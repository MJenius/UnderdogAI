import sys
import subprocess
import os

def strip_runtime_guards(path):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    filtered_lines = []
    skip_grpc_guard = False

    for line in lines:
        if "from google.protobuf import runtime_version" in line:
            continue
        if line.startswith("_runtime_version.ValidateProtobufRuntimeVersion("):
            continue
        if line.startswith("GRPC_GENERATED_VERSION = "):
            skip_grpc_guard = True
            continue
        if skip_grpc_guard:
            if line.startswith("class "):
                skip_grpc_guard = False
                filtered_lines.append(line)
            continue
        filtered_lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(filtered_lines)

def compile_and_strip():
    proto_dir = os.path.dirname(os.path.abspath(__file__))
    proto_file = os.path.join(proto_dir, "simulation.proto")
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        proto_file
    ]
    subprocess.run(cmd, check=True)
    
    pb2_path = os.path.join(proto_dir, "simulation_pb2.py")
    pb2_grpc_path = os.path.join(proto_dir, "simulation_pb2_grpc.py")
    
    for path in [pb2_path, pb2_grpc_path]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            stripped_lines = [line for line in lines if not line.strip().startswith("#")]
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(stripped_lines)

    strip_runtime_guards(pb2_path)
    strip_runtime_guards(pb2_grpc_path)

if __name__ == "__main__":
    compile_and_strip()
