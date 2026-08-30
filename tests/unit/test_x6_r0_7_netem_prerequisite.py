from __future__ import annotations
import pytest
from src.expansion.x6_r0_7_netem_prerequisite import X6R07NetemPrerequisiteError, validate_netem_prerequisite

def _record(stdout: str, return_code: int = 0, stderr: str = "") -> dict[str, object]: return {"stdout": stdout, "stderr": stderr, "return_code": return_code}
def _records() -> dict[str, object]:
 return {"kernel":_record("6.18.33.2-microsoft-standard-WSL2\n"),"kernel_config":_record("CONFIG_NET_SCH_NETEM=m\n"),"module":_record("name:           sch_netem\nvermagic:       6.18.33.2-microsoft-standard-WSL2 SMP\n"),"loaded_modules":_record("sch_netem 20480 0\n"),"image_identity":_record("sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c"),"tc_version":_record("tc utility, iproute2-6.1.0, libbpf 1.3.0\n"),"iproute2_package":_record("iproute2 6.1.0-1ubuntu6.4\n"),"capability":_record("CapEff: 00000000a80435fb\n"),"active_qdisc":_record('[{"kind":"netem","handle":"10:"},{"kind":"pfifo","handle":"20:"}]\n'),"restored_qdisc":_record('[{"kind":"noqueue","handle":"0:"}]\n')}
def test_accepts_loaded_module_and_exact_disposable_chain() -> None:
 result=validate_netem_prerequisite(_records()); assert result["status"]=="NETEM_PREREQUISITE_VALIDATED"; assert result["operator_action_required_after_wsl_restart"]=="sudo modprobe sch_netem"
@pytest.mark.parametrize(("name","replacement","prefix"),[("loaded_modules",_record(""),"MODULE_UNAVAILABLE"),("tc_version",_record("tc unavailable\n"),"USERSPACE_QDISC_UNAVAILABLE"),("capability",_record(""),"PERMISSION_FAILURE"),("active_qdisc",_record('[{"kind":"noqueue","handle":"0:"}]'),"USERSPACE_QDISC_UNAVAILABLE"),("kernel",_record("",2,"missing"),"COMMAND_REJECTED")])
def test_fails_closed_with_distinct_prerequisite_classes(name: str, replacement: dict[str, object], prefix: str) -> None:
 records=_records();records[name]=replacement
 with pytest.raises(X6R07NetemPrerequisiteError,match="^"+prefix): validate_netem_prerequisite(records)
