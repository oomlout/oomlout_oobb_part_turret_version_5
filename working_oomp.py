"""Materialize each source record synchronously before working_svg reads it."""
from pathlib import Path

import oomp
import yaml
from working_oomp_populate import catalogue_records


def main(**kwargs):
    project = Path(__file__).resolve().parent
    for source in catalogue_records(stage="parts_source", **kwargs):
        part_id = source.parent.name
        record = yaml.safe_load(source.read_text(encoding="utf-8"))
        destination = project / "parts" / part_id
        manual = destination / "working_manual.yaml"
        if manual.is_file():
            record.update(yaml.safe_load(manual.read_text(encoding="utf-8")) or {})
        result = oomp.add_part(**record, make_files=False)
        if result["id"] != part_id:
            raise ValueError(f"Part taxonomy disagrees with source folder {part_id}")
        for field in ("id", "directory", "md5", "md5_6", "md5_6_alpha"):
            record[field] = result[field]
        destination.mkdir(parents=True, exist_ok=True)
        contents = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
        (destination / "working.yaml").write_text(contents, encoding="utf-8")


load_parts = main


if __name__ == "__main__":
    main()
