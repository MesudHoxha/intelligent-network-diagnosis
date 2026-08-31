from __future__ import annotations
import json
from pathlib import Path
import pytest
from src.collection.x6_performance_collector import aggregate_windows, derive_window, exact_fault_hierarchy, exact_noqueue, parse_iperf3, qdisc_dropped, validate_speed_pair
import src.collection.x6_performance_collector as performance_collector
from src.collection.x6_r0_3_pre_runtime_validation import build_threshold_manifest
from src.fault_injection.x6_packet_loss import apply_mutation, planned_journal, recover
from src.fault_injection.phase6_common import write_json_atomic
from src.expansion.x6_r1_performance_rule import diagnose_x6_r1
from src.expansion.x6_r1_runtime_context import load_x6_r1_runtime_context
from src.orchestration.x6_r1_packet_loss_runner import _topology_preflight,_within_restored_baseline,canonical_threshold_baselines,verify_x6_r0_7_host_netem_prerequisite,wait_for_baseline_health

ROOT=Path(__file__).resolve().parents[2]
def record(stdout="",rc=0): return {"return_code":rc,"stdout":stdout,"stderr":"","command":[]}
def qdisc(rows): return record(json.dumps(rows))
def filters(): return [qdisc([]),qdisc([])]

def test_iperf_parser_fails_closed_and_accepts_sum_received():
 assert parse_iperf3(record('{"end":{"sum_received":{"bits_per_second":123000000}}}'))["value"]==123.0
 assert parse_iperf3(record("{}"))["availability"]=="collection_unavailable"
 assert parse_iperf3(record("",124))["availability"]=="collection_unavailable"

def test_qdisc_ownership_is_exact():
 no=qdisc([{"kind":"noqueue","handle":"0:"}]); fault=qdisc([{"kind":"netem","handle":"10:","stats":{"drops":9}},{"kind":"pfifo","handle":"20:","parent":"10:1","stats":{"drops":0}}])
 assert exact_noqueue(no,filters()) and exact_fault_hierarchy(fault)
 assert qdisc_dropped(fault,kind="netem",handle="10:")==9 and qdisc_dropped(fault,kind="pfifo",handle="20:")==0

def test_queue_drop_count_records_structural_and_counter_provenance(monkeypatch):
 monkeypatch.setattr(performance_collector,"parse_iputils_ping_probe",lambda record:{"packet_loss_ratio":{"availability":"observed","value":0.0},"round_trip_latency_ms_p95":{"availability":"observed","value":1.0}})
 monkeypatch.setattr(performance_collector,"parse_iperf3",lambda record:{"availability":"observed","value":100.0})
 common={"ping":record(),"iperf":record(),"r2_tx_before":record("0"),"r2_tx_after":record("100"),"r3_rx_before":record("0"),"r3_rx_after":record("100"),"elapsed_seconds":1.0,"filters_before":filters(),"filters_after":filters()}
 no=qdisc([{"kind":"noqueue","handle":"0:"}]); healthy=derive_window({**common,"qdisc_before":no,"qdisc_after":no},phase="baseline",speed_mbps=10000)
 fault=qdisc([{"kind":"netem","handle":"10:","stats":{"drops":9}},{"kind":"pfifo","handle":"20:","parent":"10:1","stats":{"drops":0}}]); fault_row=derive_window({**common,"qdisc_before":fault,"qdisc_after":fault},phase="fault",speed_mbps=10000)
 assert healthy["queue_drop_count"]=={"availability":"observed","value":0,"derivation":"STRUCTURAL_ZERO_NO_MANAGED_QUEUE"}
 assert fault_row["queue_drop_count"]=={"availability":"observed","value":0,"derivation":"COUNTER_DELTA_CHILD_PFIFO_20"}

def test_speed_requires_equal_direct_and_ethtool_provenance():
 assert validate_speed_pair(record("10000\n"),record("10000\n"),record("Speed: 10000Mb/s\n"),record("Speed: 10000Mb/s\n"))==10000
 with pytest.raises(RuntimeError): validate_speed_pair(record("10000"),record("1000"),record("Speed: 10000Mb/s"),record("Speed: 1000Mb/s"))

def _threshold():
 values={"packet_loss_ratio":[0.0]*10,"round_trip_latency_ms_p95":[1.0]*10,"throughput_mbps":[100.0]*10,"interface_utilization_ratio":[.1]*10,"queue_drop_count":[0]*10}
 return build_threshold_manifest(values,topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH",traffic_context_id="X6_TRAFFIC_01_FROZEN_TCP_AND_PING")

def test_threshold_inputs_are_canonicalized_before_semantic_manifest_validation():
 values={"packet_loss_ratio":[0.0]*10,"round_trip_latency_ms_p95":[0.06350049]*10,"throughput_mbps":[7997.5869369]*10,"interface_utilization_ratio":[0.73620751]*10,"queue_drop_count":[0]*10}
 canonical=canonical_threshold_baselines(values)
 assert canonical["interface_utilization_ratio"]==["0.736208"]*10
 manifest=build_threshold_manifest(canonical,topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH",traffic_context_id="X6_TRAFFIC_01_FROZEN_TCP_AND_PING")
 assert manifest["features"][3]["sorted_baseline_values"]==["0.736208"]*10
def _vector(values=None):
 values=values or {"packet_loss_ratio":.1,"round_trip_latency_ms_p95":1.0,"throughput_mbps":100.0,"interface_utilization_ratio":.1,"queue_drop_count":0,"rate_limit_detected":False}
 catalog=json.loads((ROOT/"plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
 return {"schema_version":2,"vector_id":"synthetic-x6-r1-source-test","catalog_id":catalog["catalog_id"],"evidence_id":"synthetic-source-test","values":{name:{"value":value,"availability":"observed"} for name,value in values.items()},"mask_id":None,"provenance":{"evidence_sha256":"0"*64,"feature_catalog_sha256":__import__('hashlib').sha256((ROOT/"plans/expansion/X1_FEATURE_CATALOG_V1.json").read_bytes()).hexdigest()}}
def test_rule_diagnoses_exact_conditional_signature_and_abstains():
 result=diagnose_x6_r1(_vector(),_threshold(),repository_root=ROOT); assert result["status"]=="diagnosed" and result["explanation_refs"]==["rule:R_X6_PERFORMANCE_001"]
 bad=_vector();bad["values"]["packet_loss_ratio"]={"value":0.0,"availability":"observed"};assert diagnose_x6_r1(bad,_threshold(),repository_root=ROOT)["status"]=="abstained"
 missing=_vector();missing["values"]["throughput_mbps"]={"value":None,"availability":"collection_unavailable"};assert diagnose_x6_r1(missing,_threshold(),repository_root=ROOT)["status"]=="insufficient_evidence"

def test_mutation_journal_is_durable_before_commands_and_partial_recovery(tmp_path):
 context=load_x6_r1_runtime_context(ROOT); (tmp_path/"mutation").mkdir(); write_json_atomic(tmp_path/"mutation/action_journal.json",planned_journal(context)); calls=[]
 def execute(command): calls.append(command); return record()
 apply_mutation(tmp_path,context,execute); journal=json.loads((tmp_path/"mutation/action_journal.json").read_text()); assert journal["events"][0]["state"]=="PLANNED" and journal["actions"][0]["status"]=="COMMAND_ACCEPTED"
 snapshots=iter([qdisc([{"kind":"netem","handle":"10:"}]),qdisc([{"kind":"noqueue","handle":"0:"}])])
 def restore_execute(command): return next(snapshots) if command==context["qdisc"]["capture_command"] else qdisc([]) if command in context["qdisc"]["filter_commands"] else record()
 assert recover(tmp_path,context,restore_execute)["status"]=="RESTORATION_CONFIRMED"

def test_three_window_aggregation_rejects_unavailable():
 row={name:{"availability":"observed","value":False if name=="rate_limit_detected" else 0} for name in ("packet_loss_ratio","round_trip_latency_ms_p95","throughput_mbps","interface_utilization_ratio","queue_drop_count","rate_limit_detected")}
 assert aggregate_windows([row,row,row])["queue_drop_count"]["value"]==0
 broken={key:dict(value) for key,value in row.items()};broken["throughput_mbps"]={"availability":"collection_unavailable","value":None};assert all(value["availability"]=="collection_unavailable" for value in aggregate_windows([row,broken,row]).values())

def test_restored_windows_must_all_satisfy_frozen_baseline():
 row={"packet_loss_ratio":{"availability":"observed","value":0.0},"round_trip_latency_ms_p95":{"availability":"observed","value":1.0},"throughput_mbps":{"availability":"observed","value":100.0},"interface_utilization_ratio":{"availability":"observed","value":.1},"queue_drop_count":{"availability":"observed","value":0},"rate_limit_detected":{"availability":"observed","value":False}}
 assert _within_restored_baseline([row,row,row],_threshold())
 bad={key:dict(value) for key,value in row.items()};bad["packet_loss_ratio"]["value"]=.5
 assert not _within_restored_baseline([row,bad,row],_threshold())

def test_baseline_health_waits_for_routes_forwarding_and_reachability_without_fixed_sleep():
 calls={"ping":0}
 def execute(command):
  if "ping" in command:
   calls["ping"]+=1
   return record("",0 if calls["ping"]>1 else 1)
  if "sysctl" in command:return record("1\n")
  if command[-3:-1]==["route","get"]:return record("10.61.3.2 dev eth1 src 10.61.1.2\n")
  return record()
 result=wait_for_baseline_health(execute,timeout_seconds=.1,poll_seconds=0)
 assert result["status"]=="BASELINE_HEALTHY" and len(result["attempts"])==2

def test_x6_r0_7_host_netem_preflight_is_verify_only_and_fails_closed():
 def execute(command):
  text={"uname -r":"6.18.33.2-microsoft-standard-WSL2\n","bash -lc zgrep CONFIG_NET_SCH_NETEM /proc/config.gz":"CONFIG_NET_SCH_NETEM=m\n","modinfo sch_netem":"name:           sch_netem\nvermagic:       6.18.33.2-microsoft-standard-WSL2 SMP\n","lsmod":"sch_netem 20480 0\n"}[" ".join(command)]
  return record(text)
 result=verify_x6_r0_7_host_netem_prerequisite(execute)
 assert result["status"]=="X6_R0_7_HOST_NETEM_PREREQUISITE_VERIFIED" and result["policy"]=="VERIFY_ONLY_NEVER_PRIVILEGED_MODULE_LOAD"
 with pytest.raises(RuntimeError,match="MODULE_UNAVAILABLE"):
  verify_x6_r0_7_host_netem_prerequisite(lambda command:record("",1))

def test_corrected_topology_overlay_preserves_management_defaults_and_experiment_routes():
 context=load_x6_r1_runtime_context(ROOT)
 def execute(command):
  if command[-3:]==["route","show","default"]: return record(json.dumps([{"dst":"default","gateway":"172.20.20.1","dev":"eth0"}]))
  if command[-3:-1]==["route","get"]:
   destination=command[-1];node=command[2].removeprefix("clab-x6r1-")
   rows={
    ("hosta","10.61.3.2"):("10.61.1.1","eth1","10.61.1.2"),("hostb","10.61.1.2"):("10.61.3.1","eth1","10.61.3.2"),
    ("r1","10.61.3.2"):("10.61.12.2","eth2","10.61.12.1"),("r2","10.61.3.2"):("10.61.23.2","eth2","10.61.23.1"),
    ("r2","10.61.1.2"):("10.61.12.1","eth1","10.61.12.2"),("r3","10.61.1.2"):("10.61.23.1","eth1","10.61.23.2")}
   via,dev,src=rows[(node,destination)];return record(json.dumps([{"dst":destination,"gateway":via,"dev":dev,"prefsrc":src}]))
  if command[-3:-1]==["link","show"]: return record(json.dumps([{"flags":["UP"]}]))
  return record("version")
 preflight=_topology_preflight(execute,context)
 assert set(preflight["experiment_routes"])=={"hosta_forward","hostb_reverse","r1_forward","r2_forward","r2_reverse","r3_reverse"}
