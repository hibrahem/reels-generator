"""The trim+concat filtergraph used to keep only the non-silent segments."""

from reels.domain.shared.value_objects import TimeRange
from reels.infrastructure.ffmpeg.ffmpeg_segment_cutter import segments_filtergraph


def test_two_segments_trim_and_concat_with_reset_timestamps():
    fc = segments_filtergraph([TimeRange(0.0, 4.15), TimeRange(5.85, 10.0)])
    assert fc == (
        "[0:v]trim=start=0.000:end=4.150,setpts=PTS-STARTPTS[v0];"
        "[0:a]atrim=start=0.000:end=4.150,asetpts=PTS-STARTPTS[a0];"
        "[0:v]trim=start=5.850:end=10.000,setpts=PTS-STARTPTS[v1];"
        "[0:a]atrim=start=5.850:end=10.000,asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
    )


def test_single_segment_still_concats_to_the_output_labels():
    fc = segments_filtergraph([TimeRange(1.0, 2.0)])
    assert fc.endswith("concat=n=1:v=1:a=1[vout][aout]")
