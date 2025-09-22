import subprocess
import json
import sys

def get_all_terraform_outputs():
    try:
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'terraform')
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error getting terraform outputs: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    outputs = get_all_terraform_outputs()
    print(json.dumps(outputs, indent=2))