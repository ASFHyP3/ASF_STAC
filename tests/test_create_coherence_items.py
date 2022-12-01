from datetime import datetime, timedelta

from shapely import geometry

import create_coherence_items
from create_coherence_items import SEASONS


def test_season_datetime_averages():
    assert SEASONS['winter']['datetime'] - SEASONS['winter']['start_datetime'] \
        == SEASONS['winter']['end_datetime'] - SEASONS['winter']['datetime'] \
        == timedelta(days=44, seconds=43200)

    assert SEASONS['spring']['datetime'] - SEASONS['spring']['start_datetime'] \
           == SEASONS['spring']['end_datetime'] - SEASONS['spring']['datetime'] \
           == timedelta(days=45, seconds=43200)

    assert SEASONS['summer']['datetime'] - SEASONS['summer']['start_datetime'] \
           == SEASONS['summer']['end_datetime'] - SEASONS['summer']['datetime'] \
           == timedelta(days=45, seconds=43200)

    assert SEASONS['fall']['datetime'] - SEASONS['fall']['start_datetime'] \
           == SEASONS['fall']['end_datetime'] - SEASONS['fall']['datetime'] \
           == timedelta(days=45)


def test_jsonify_stac_item():
    assert create_coherence_items.jsonify_stac_item(
        {
            'str_field': 'foo',
            'int_field': 5,
            'float_field': 3.1,
            'bool_field': True,
            'null_field': None,
            'dict_field': {'str_field': 'bar'},
            'list_field': [[1, 2], [3, 4]],
            'tuple_field': ((1, 2), (3, 4)),
            'datetime_field': datetime(2022, 11, 30, 12),
        }
    ) == (
        '{"str_field": "foo", "int_field": 5, "float_field": 3.1, "bool_field": true, "null_field": null, '
        '"dict_field": {"str_field": "bar"}, "list_field": [[1, 2], [3, 4]], "tuple_field": [[1, 2], [3, 4]], '
        '"datetime_field": "2022-11-30T12:00:00Z"}'
    )


def test_create_stac_item_N00E005_124D_inc():
    assert create_coherence_items.create_stac_item('data/tiles/N00E005/N00E005_124D_inc.tif', 'foo.com/') \
           == {
               'type': 'Feature',
               'stac_version': '1.0.0',
               'id': 'N00E005_124D_inc',
               'properties': {
                   'tile': 'N00E005',
                   'sar:instrument_mode': create_coherence_items.SAR_INSTRUMENT_MODE,
                   'sar:frequency_band': create_coherence_items.SAR_FREQUENCY_BAND,
                   'sar:product_type': 'inc',
                   'start_datetime': datetime(2019, 12, 1),
                   'end_datetime': datetime(2020, 11, 30),
               },
               'geometry': {
                   'type': 'Polygon',
                   'coordinates': (
                       (
                           (6.0, -1.0),
                           (6.0, 0.0),
                           (5.0, 0.0),
                           (5.0, -1.0),
                           (6.0, -1.0),
                       ),
                   ),
               },
               'assets': {
                   'data': {
                       'href': 'foo.com/data/tiles/N00E005/N00E005_124D_inc.tif',
                       'type': 'image/tiff; application=geotiff',
                   },
               },
               'bbox': (5, -1, 6, 0),
               'stac_extensions': ['https://stac-extensions.github.io/sar/v1.0.0/schema.json'],
               'collection': create_coherence_items.COLLECTION_ID,
           }


def test_create_stac_item_S78W078_summer_hh_AMP():
    assert create_coherence_items.create_stac_item('data/tiles/S78W078/S78W078_summer_hh_AMP.tif', 'bar.com/') \
           == {
               'type': 'Feature',
               'stac_version': '1.0.0',
               'id': 'S78W078_summer_hh_AMP',
               'properties': {
                   'tile': 'S78W078',
                   'sar:instrument_mode': create_coherence_items.SAR_INSTRUMENT_MODE,
                   'sar:frequency_band': create_coherence_items.SAR_FREQUENCY_BAND,
                   'sar:polarizations': ['HH'],
                   'sar:product_type': 'AMP',
                   'start_datetime': datetime(2020, 6, 1),
                   'end_datetime': datetime(2020, 8, 31),
                   'datetime': datetime(2020, 7, 16, 12),
                   'season': 'summer',
               },
               'geometry': {
                   'type': 'Polygon',
                   'coordinates': (
                       (
                           (-77.0, -79.0),
                           (-77.0, -78.0),
                           (-78.0, -78.0),
                           (-78.0, -79.0),
                           (-77.0, -79.0),
                       ),
                   ),
               },
               'assets': {
                   'data': {
                       'href': 'bar.com/data/tiles/S78W078/S78W078_summer_hh_AMP.tif',
                       'type': 'image/tiff; application=geotiff',
                   },
               },
               'bbox': (-78, -79, -77, -78),
               'stac_extensions': ['https://stac-extensions.github.io/sar/v1.0.0/schema.json'],
               'collection': create_coherence_items.COLLECTION_ID,
           }


def test_parse_s3_key():
    assert create_coherence_items.parse_s3_key('data/tiles/N00E005/N00E005_124D_inc.tif') \
        == create_coherence_items.ItemMetadata(
            id='N00E005_124D_inc',
            bbox=geometry.box(5, -1, 6, 0),
            tile='N00E005',
            product='inc',
        )

    assert create_coherence_items.parse_s3_key('data/tiles/N00E005/N00E005_fall_vh_AMP.tif') \
        == create_coherence_items.ItemMetadata(
            id='N00E005_fall_vh_AMP',
            bbox=geometry.box(5, -1, 6, 0),
            tile='N00E005',
            product='AMP',
            extra=create_coherence_items.ExtraItemMetadata(
                season='fall',
                start_datetime=datetime(2020, 9, 1),
                end_datetime=datetime(2020, 11, 30),
                datetime=datetime(2020, 10, 16, 0),
                polarization='VH',
            ),
        )

    assert create_coherence_items.parse_s3_key('data/tiles/N00E011/N00E011_winter_vv_COH36.tif') \
        == create_coherence_items.ItemMetadata(
            id='N00E011_winter_vv_COH36',
            bbox=geometry.box(11, -1, 12, 0),
            tile='N00E011',
            product='COH36',
            extra=create_coherence_items.ExtraItemMetadata(
                season='winter',
                start_datetime=datetime(2019, 12, 1),
                end_datetime=datetime(2020, 2, 28),
                datetime=datetime(2020, 1, 14, 12),
                polarization='VV',
            ),
        )


def test_item_id_from_s3_key():
    assert create_coherence_items.item_id_from_s3_key('path/to/key.tif') == 'key'


def test_bounding_box_from_tile():
    assert create_coherence_items.bounding_box_from_tile('N49E009') \
           == geometry.box(9, 48, 10, 49)

    assert create_coherence_items.bounding_box_from_tile('N48W090') \
        == geometry.box(-90, 47, -89, 48)

    assert create_coherence_items.bounding_box_from_tile('S01E012') \
        == geometry.box(12, -2, 13, -1)

    assert create_coherence_items.bounding_box_from_tile('S78W161') \
        == geometry.box(-161, -79, -160, -78)
