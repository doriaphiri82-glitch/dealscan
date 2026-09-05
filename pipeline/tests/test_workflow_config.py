from pathlib import Path


def test_scheduled_pipeline_tests_set_pythonpath():
    """The scheduled workflow runs pytest from pipeline/, so top-level modules must be importable."""
    workflow = Path(__file__).parents[2] / ".github" / "workflows" / "scrape.yml"
    text = workflow.read_text(encoding="utf-8")

    marker = "- name: Run pipeline tests"
    start = text.index(marker)
    end = text.index("      - name:", start + len(marker))
    step = text[start:end]

    assert "working-directory: pipeline" in step
    assert "env:\n          PYTHONPATH: ." in step
