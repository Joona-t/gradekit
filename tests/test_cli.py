import make_test_frame as mtf
from gradekit import lut
from gradekit.cli import main


def test_cli_analyze_image_end_to_end(tmp_path, capsys):
    frame = tmp_path / "frame.png"
    info = mtf.make(str(frame))
    out_cube = tmp_path / "out.cube"
    preview = tmp_path / "before_after.png"
    nx, ny, nw, nh = info["neutral"]

    rc = main([
        "analyze", str(frame),
        "--neutral", f"{nx},{ny},{nw},{nh}",
        "--lut", str(out_cube),
        "--preview", str(preview),
        "--size", "17",
    ])

    assert rc == 0
    assert out_cube.exists()
    ok, size_seen, rows_seen, problems = lut.validate_cube(str(out_cube))
    assert ok, problems
    assert size_seen == 17
    assert rows_seen == 17 ** 3
    assert preview.exists()

    out = capsys.readouterr().out
    assert "WHITE BALANCE" in out
    assert "EXPOSURE" in out
    assert ".cube" in out or "out.cube" in out


def test_cli_missing_file_is_friendly(capsys):
    rc = main(["analyze", "/no/such/file.mov"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "gradekit:" in err
