import argparse
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Optional

import boto3
from shapely import geometry

import asf_stac_util


s3 = boto3.client('s3')

# TODO verify the start and end datetime values for each season
# TODO verify UTC
SEASONS = {
    'winter': {
        'start_datetime': datetime(2019, 12, 1, tzinfo=timezone.utc),
        'end_datetime': datetime(2020, 2, 28, tzinfo=timezone.utc),
        'datetime': datetime(2020, 1, 14, 12, tzinfo=timezone.utc),
    },
    'spring': {
        'start_datetime': datetime(2020, 3, 1, tzinfo=timezone.utc),
        'end_datetime': datetime(2020, 5, 31, tzinfo=timezone.utc),
        'datetime': datetime(2020, 4, 15, 12, tzinfo=timezone.utc),
    },
    'summer': {
        'start_datetime': datetime(2020, 6, 1, tzinfo=timezone.utc),
        'end_datetime': datetime(2020, 8, 31, tzinfo=timezone.utc),
        'datetime': datetime(2020, 7, 16, 12, tzinfo=timezone.utc),
    },
    'fall': {
        'start_datetime': datetime(2020, 9, 1, tzinfo=timezone.utc),
        'end_datetime': datetime(2020, 11, 30, tzinfo=timezone.utc),
        'datetime': datetime(2020, 10, 16, 0, tzinfo=timezone.utc),
    },
}

COLLECTION_ID = 'sentinel-1-global-coherence'
SAR_INSTRUMENT_MODE = 'IW'
SAR_FREQUENCY_BAND = 'C'


@dataclass(frozen=True)
class ExtraItemMetadata:
    season: str
    start_datetime: datetime
    end_datetime: datetime
    datetime: datetime
    polarization: str


@dataclass(frozen=True)
class ItemMetadata:
    id: str
    bbox: geometry.Polygon
    tile: str
    product: str
    extra: Optional[ExtraItemMetadata] = None


def get_s3_url() -> str:
    bucket = 'sentinel-1-global-coherence-earthbigdata'
    location = s3.get_bucket_location(Bucket=bucket)['LocationConstraint']
    return f'https://{bucket}.s3.{location}.amazonaws.com/'


def write_stac_items(s3_keys: list[str], s3_url: str, output_file: Path) -> None:
    with output_file.open('w') as f:
        for count, s3_key in enumerate(s3_keys, start=1):
            print(f'Creating STAC items: {count}/{len(s3_keys)}', end='\r')
            stac_item = create_stac_item(s3_key, s3_url)
            f.write(asf_stac_util.jsonify_stac_item(stac_item) + '\n')


def create_stac_item(s3_key: str, s3_url: str) -> dict:
    metadata = parse_s3_key(s3_key)
    item = {
        'type': 'Feature',
        'stac_version': '1.0.0',
        'id': metadata.id,
        'properties': {
            'tile': metadata.tile,
            'sar:instrument_mode': SAR_INSTRUMENT_MODE,
            'sar:frequency_band': SAR_FREQUENCY_BAND,
            'sar:product_type': metadata.product,  # TODO this was hard-coded to COH in Forrest's stac ext code?
            'start_datetime': SEASONS['winter']['start_datetime'],
            'end_datetime': SEASONS['fall']['end_datetime'],
        },
        'geometry': geometry.mapping(metadata.bbox),
        'assets': {
            'data': {
                'href': urllib.parse.urljoin(s3_url, s3_key),
                'type': 'image/tiff; application=geotiff',
            },
        },
        'bbox': metadata.bbox.bounds,
        'stac_extensions': ['https://stac-extensions.github.io/sar/v1.0.0/schema.json'],
        'collection': COLLECTION_ID,
    }
    if metadata.extra:
        item['properties'].update(
            {
                'season': metadata.extra.season,
                'start_datetime': metadata.extra.start_datetime,
                'end_datetime': metadata.extra.end_datetime,
                'datetime': metadata.extra.datetime,
                'sar:polarizations': [metadata.extra.polarization],
            }
        )
    return item


def parse_s3_key(s3_key: str) -> ItemMetadata:
    item_id = PurePath(s3_key).stem
    parts = item_id.split('_')
    if len(parts) == 3:
        tile, _, product = parts
        bbox = bounding_box_from_tile(tile)
        metadata = ItemMetadata(
            id=item_id,
            bbox=bbox,
            tile=tile,
            product=product,
        )
    else:
        tile, season, polarization, product = parts
        bbox = bounding_box_from_tile(tile)
        metadata = ItemMetadata(
            id=item_id,
            bbox=bbox,
            tile=tile,
            product=product,
            extra=ExtraItemMetadata(
                season=season,
                start_datetime=SEASONS[season]['start_datetime'],
                end_datetime=SEASONS[season]['end_datetime'],
                datetime=SEASONS[season]['datetime'],
                polarization=polarization.upper(),
            ),
        )
    return metadata


def bounding_box_from_tile(tile: str) -> geometry.Polygon:
    # "Tiles in the data set are labeled by the upper left coordinate of each 1x1 degree tile"
    # http://sentinel-1-global-coherence-earthbigdata.s3-website-us-west-2.amazonaws.com/#organization

    lat = tile[0]
    latval = int(tile[1:3])

    lon = tile[3]
    lonval = int(tile[4:7])

    max_y = latval if lat == 'N' else -latval
    min_y = max_y - 1

    min_x = lonval if lon == 'E' else -lonval
    max_x = min_x + 1

    return geometry.box(min_x, min_y, max_x, max_y)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('s3_objects', type=Path, help='Path to a text file containing the list of S3 objects')
    parser.add_argument(
        '-o', '--output-file', type=Path, help='Path for the output file', default='sentinel-1-global-coherence.ndjson'
    )
    parser.add_argument('-n', '--number-of-items', type=int, help='Number of items to create')
    return parser.parse_args()


def main():
    args = parse_args()

    with args.s3_objects.open() as f:
        s3_keys = f.read().splitlines()[: args.number_of_items]

    s3_url = get_s3_url()
    write_stac_items(s3_keys, s3_url, args.output_file)


if __name__ == '__main__':
    main()
