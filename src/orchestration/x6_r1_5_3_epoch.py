"""Strict, audited kernel/sch_netem projection; raw evidence is never rewritten."""
from pathlib import PurePosixPath, Path
import re
from src.orchestration.x6_r1_5_1_contract import require, digest

VERSION="KERNEL_SCH_NETEM_INVARIANTS_V1"

def lines(raw):
    require(isinstance(raw,str) and raw.isascii(),"non-ASCII module observation")
    require(all(32<=ord(c)<=126 or c in "\n\t" for c in raw),"module control character")
    parts=raw.split("\n")
    if parts[-1]=="":parts.pop()
    require(parts and all(parts),"empty module observation line")
    return parts

def modinfo(raw):
    values={}
    prior=None
    required={"name","filename","vermagic"}
    for line in lines(raw):
        if line[0] in " \t":
            payload=line.lstrip(" \t").rstrip(" \t")
            require(prior is not None and prior not in required and payload,
                    "invalid modinfo continuation")
            values[prior][-1]+=" "+payload
            continue
        match=re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):(.*)",line)
        require(match is not None,"malformed modinfo line")
        label, value=match.groups()
        value=value.lstrip(" \t").rstrip(" \t")
        require(label not in values or label in {"alias","parm"},"duplicate modinfo label")
        require(label not in required or value,"empty required modinfo field")
        values.setdefault(label,[]).append(value)
        prior=label
    require(required<=values.keys(),"missing required modinfo field")
    return values

def modules(raw):
    parts=lines(raw)
    require(re.fullmatch(r"Module[ \t]+Size[ \t]+Used[ \t]+by",parts[0]),
            "invalid lsmod header")
    result={}
    for line in parts[1:]:
        match=re.fullmatch(r"([A-Za-z0-9_]+)[ \t]+([0-9]+)[ \t]+([0-9]+)(?:[ \t]+([A-Za-z0-9_]+(?:,[A-Za-z0-9_]+)*))?[ \t]*",line)
        require(match is not None,"malformed lsmod row")
        name,size,used,users=match.groups()
        require(name not in result,"duplicate lsmod module")
        result[name]={"size":int(size),"used":int(used),"users":users}
    return result

def normalized_kernel(observed, *, allow_ineligible=False):
    require(set(observed)=={"kernel","kernel_config","module","module_provenance"},
            "kernel observation schema")
    kernel_lines=lines(observed["kernel"])
    require(len(kernel_lines)==1 and kernel_lines[0]==kernel_lines[0].strip()
            and kernel_lines[0],"kernel release schema")
    kernel=kernel_lines[0]
    configs=lines(observed["kernel_config"])
    require(len(configs)==1 and re.fullmatch(r"CONFIG_NET_SCH_NETEM=[myn]",configs[0]),
            "kernel config schema")
    info=modinfo(observed["module_provenance"])
    loaded=modules(observed["module"])
    name=info["name"][0]
    require(name=="sch_netem","required module identity")
    filename=info["filename"][0]
    require(filename.startswith("/") and all(part not in {".","..",""} for part in filename.split("/")[1:])
            and str(PurePosixPath(filename))==filename,"module filename syntax")
    vermagic=" ".join(re.split(r"[ \t]+",info["vermagic"][0]))
    compatible=vermagic.split()[0]==kernel
    expected="/lib/modules/"+kernel+"/kernel/net/sched/sch_netem.ko"
    valid=configs[0]=="CONFIG_NET_SCH_NETEM=m" and "sch_netem" in loaded and compatible and filename==expected
    require(allow_ineligible or valid,"required module readiness/provenance")
    return {"running_kernel_release":kernel,"kernel_config_net_sch_netem":configs[0],
            "required_module_name":name,"required_module_loaded":"sch_netem" in loaded,
            "required_module_filename":filename,"required_module_vermagic":vermagic}

def projection_binding(fields):
    return {"version":VERSION,"parser_sha256":digest(Path(__file__).read_bytes()),"invariants":fields}

def difference(left,right):
    """No status assertions: callers supply independently validated epoch contexts."""
    nonboot=lambda value:{k:v for k,v in value.items() if k!="boot_id"}
    if nonboot(left)!=nonboot(right):return "NOT_RUN_ENVIRONMENT_DRIFT"
    if left["boot_id"]!=right["boot_id"]:return "NOT_RUN_OPERATIONAL_FAILURE"
    return None
