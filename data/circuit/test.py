import os


def get_files_in_dir(dir_path: str):
    """Get all files in a directory."""
    return [
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if os.path.isfile(os.path.join(dir_path, f))
    ]


if __name__ == "__main__":
    files = get_files_in_dir(os.path.dirname(__file__))

    without_det_or_rand = [
        file.replace("_det.in", "").replace("_rand.in", "") for file in files
    ]

    for prefix in without_det_or_rand:
        if not os.path.exists(prefix + "_det.in") or not os.path.exists(
            prefix + "_rand.in"
        ):
            continue
        if "siteconfig" in prefix:
            continue
        print(f"Processing {prefix}")

        file_det, file_rand = "", ""
        with open(prefix + "_det.in", "r") as f:
            file_det = f.read()
        with open(prefix + "_rand.in", "r") as f:
            file_rand = f.read()

        assert file_det != file_rand, "Files should not be the same"

    print("All files processed successfully. No duplicates found.")
