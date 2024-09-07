from pathlib import Path

from platformdirs import user_config_path as get_user_config_path

import basilisk.global_vars as global_vars

user_config_path = get_user_config_path(
	"basilisk", "basilisk_llm", roaming=True, ensure_exists=True
)


def get_config_file_paths(file_path: str) -> list[Path]:
	search_config_paths = []
	if global_vars.user_data_path:
		search_config_paths.append(global_vars.user_data_path / file_path)
	search_config_paths.append(user_config_path / file_path)
	return search_config_paths
	return search_config_paths


def search_existing_path(paths: list[Path]) -> Path:
	for p in paths:
		if p.exists() or p.parent.exists():
			return p
	return paths[-1]
