"""Guard the GHCR tag contract used by new and legacy deployments."""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci-cd.yml"

REQUIRED_TAG_TEMPLATES = (
    "${{ env.DOCKER_REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:latest",
    "${{ env.DOCKER_REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}",
    "${{ env.DOCKER_REGISTRY }}/${{ github.repository_owner }}/terraneuron-${{ matrix.service }}:latest",
    "${{ env.DOCKER_REGISTRY }}/${{ github.repository_owner }}/terraneuron-${{ matrix.service }}:${{ github.sha }}",
)


def main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    missing = [tag for tag in REQUIRED_TAG_TEMPLATES if tag not in workflow]
    if missing:
        formatted = "\n".join(f"- {tag}" for tag in missing)
        raise SystemExit(f"Missing required GHCR compatibility tags:\n{formatted}")

    print("GHCR canonical and legacy tag templates are present.")


if __name__ == "__main__":
    main()
