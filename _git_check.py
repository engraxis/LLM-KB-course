import subprocess, os

proj = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(proj, "_git_output.txt")

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=proj)
    return f"CMD: {cmd}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}\nRC: {r.returncode}\n{'='*60}\n"

results = []
results.append(run("git --no-pager status"))
results.append(run("git --no-pager log --oneline -5"))
results.append(run("git remote -v"))

with open(out, "w") as f:
    f.write("\n".join(results))

print("Output written to", out)

