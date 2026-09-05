from pathlib import Path


def test_scheduled_pipeline_tests_set_pythonpath():
    workflow = Path(__file__).parents[2] / ".github" / "workflows" / "scrape.yml"
    text = workflow.read_text(encoding="utf-8")
    marker = "- name: Run pipeline tests"
    start = text.index(marker)
    end = text.index("      - name:", start + len(marker))
    step = text[start:end]
    assert "working-directory: pipeline" in step
    assert "env:\n          PYTHONPATH: ." in step


def test_registry_accepts_arcgis_layer_metadata():
    registry = Path(__file__).parents[1] / "config" / "counties" / "registry.py"
    text = registry.read_text(encoding="utf-8")
    assert "arcgis_layer_url:Optional[str]=None" in text
    assert "extras[\"arcgis_layer_url\"]=arcgis_layer_url" in text
