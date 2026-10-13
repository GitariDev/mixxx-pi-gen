import pytest
from songdex import rekordbox

# Shapes copied from smart playlists that rekordbox 7.2.18 created itself.
NATIVE = [
    (
        "3796421800",
        '<NODE Id="-498545496" LogicalOperator="2" AutomaticUpdate="0">'
        '<CONDITION PropertyName="genre" Operator="1" ValueUnit="" ValueLeft="R&amp;B" ValueRight=""/>'
        '<CONDITION PropertyName="genre" Operator="8" ValueUnit="" ValueLeft="Soul" ValueRight=""/>'
        "</NODE>",
    ),
    (
        "465051964",
        '<NODE Id="465051964" LogicalOperator="1" AutomaticUpdate="0">'
        '<CONDITION PropertyName="year" Operator="5" ValueUnit="" ValueLeft="1980" ValueRight="1989"/>'
        "</NODE>",
    ),
    (
        "2216856871",
        '<NODE Id="-2078110425" LogicalOperator="2" AutomaticUpdate="0">'
        '<CONDITION PropertyName="myTag" Operator="8" ValueUnit="" ValueLeft="-2056124558" ValueRight=""/>'
        '<CONDITION PropertyName="myTag" Operator="8" ValueUnit="" ValueLeft="1642563157" ValueRight=""/>'
        '<CONDITION PropertyName="genre" Operator="1" ValueUnit="" ValueLeft="" ValueRight=""/>'
        "</NODE>",
    ),
]


@pytest.mark.parametrize("playlist_id,source", NATIVE)
def test_native_smart_lists_round_trip_exactly(playlist_id, source):
    parsed = rekordbox.read_smart_list(source)
    assert parsed["id"] == playlist_id
    assert (
        rekordbox.smart_list(
            playlist_id, parsed["rules"], parsed["match"], parsed["auto_update"]
        )
        == source
    )


def test_my_tag_ids_are_unsigned_in_the_dex_and_signed_in_rekordbox():
    parsed = rekordbox.read_smart_list(NATIVE[2][1])
    assert [r["left"] for r in parsed["rules"][:2]] == ["2238842738", "1642563157"]
    assert parsed["match"] == "any"


def test_smart_list_escapes_values_and_rejects_bad_rules():
    rule = {"property": "genre", "operator": 1, "left": 'Drum & "Bass" <live> /x'}
    source = rekordbox.smart_list("12", [rule])
    assert 'ValueLeft="Drum &amp; &quot;Bass&quot; &lt;live&gt; /x"' in source
    assert rekordbox.read_smart_list(source)["rules"][0]["left"] == rule["left"]
    with pytest.raises(ValueError):
        rekordbox.smart_list("12", [])
    with pytest.raises(ValueError):
        rekordbox.smart_list("12", [{"property": "mood", "operator": 1, "left": "x"}])
    with pytest.raises(ValueError):
        rekordbox.smart_list("12", [{"property": "myTag", "operator": 1, "left": "5"}])
    with pytest.raises(ValueError):
        rekordbox.smart_list("12", [{"property": "bpm", "operator": 5, "left": "120"}])


XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n\n'
    '<MASTER_PLAYLIST Version="3.0.0" AutomaticSync="0">\n'
    '  <PRODUCT Name="rekordbox" Version="7.2.18" Company="Pioneer DJ"/>\n'
    "  <PLAYLISTS>\n"
    '    <NODE Id="B9419B30" ParentId="0" Attribute="1" Timestamp="1789386432772" Lib_Type="0" CheckType="0"/>\n'
    '    <NODE Id="4B517B2B" ParentId="B9419B30" Attribute="0" Timestamp="1789386522090" Lib_Type="0" CheckType="0"/>\n'
    "  </PLAYLISTS>\n"
    "</MASTER_PLAYLIST>\n"
)


def test_register_playlists_only_appends_lines(tmp_path):
    path = tmp_path / "masterPlaylists6.xml"
    path.write_bytes(XML.encode())
    rekordbox.register_playlists(
        path, [("47368792", "root", 1), ("245248688", "47368792", 4)]
    )
    lines = path.read_text().splitlines()
    assert [line for line in XML.splitlines() if line not in lines] == []
    added = [line for line in lines if line not in XML.splitlines()]
    assert added[0].startswith('    <NODE Id="2D2CA58" ParentId="0" Attribute="1" ')
    assert added[1].startswith(
        '    <NODE Id="E9E32B0" ParentId="2D2CA58" Attribute="4" '
    )
    assert lines[-2:] == ["  </PLAYLISTS>", "</MASTER_PLAYLIST>"]
    with pytest.raises(ValueError, match="already registered"):
        rekordbox.register_playlists(path, [("47368792", "root", 1)])


def test_register_playlists_refuses_unfamiliar_layout(tmp_path):
    path = tmp_path / "masterPlaylists6.xml"
    path.write_text(
        '<MASTER_PLAYLIST><PLAYLISTS><NODE Id="1"/></PLAYLISTS></MASTER_PLAYLIST>'
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="unfamiliar layout"):
        rekordbox.register_playlists(path, [("2", "root", 0)])
    assert path.read_bytes() == before
