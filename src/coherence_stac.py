import os.path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
from itertools import repeat
from pathlib import Path

import boto3
import pystac
from pystac.extensions import sar
from shapely import geometry
from tqdm import tqdm

'''
Design:

[x] connect to aws open bucket containing coherence data
[x] ls the prefixes we're interested in
[x] parse names (N00E014_007D_inc.tif) -> bbox, season, polarization, dataset
[x] create base sentinel-1 stac item using https://github.com/stac-extensions/sar
[x] add coherence metadata to base
[x] add to catalog
[x] save catalog locally

structure:
    item (tile + season)
        inc
        lsmap
        COH(all 4)
        rho
        rmse
        tau
'''

SENTINEL1_CENTER_FREQUENCY = 5.405
SEASONS = {
    'WINTER': (datetime(2019, 12, 1), datetime(2020, 2, 28)),
    'SPRING': (datetime(2020, 3, 1), datetime(2020, 5, 31)),
    'SUMMER': (datetime(2020, 6, 1), datetime(2020, 8, 31)),
    'FALL': (datetime(2020, 9, 1), datetime(2020, 11, 30)),
}
LICENSE = 'Creative Commons Attribution 4.0 International Public License'

DATA_CITATION = (
    'Kellndorfer, J. , O. Cartus, M. Lavalle,  C. Magnard, P. Milillo, S. Oveisgharan, B. Osmanoglu, '
    'P. Rosen, and U. Wegmuller. 2022. Global seasonal Sentinel-1 interferometric coherence and backscatter data set. '
    '[Indicate subset used]. Fairbanks, Alaska USA. NASA Alaska Satellite Facility Synthetic Aperture Radar '
    'Distributed Active Archive Center. doi: https://doi.org/10.5067/8W33RRS6S2RV. [Date Accessed].'
)

LITERATURE_CITATION = (
    'Kellndorfer, J. , O. Cartus, M. Lavalle,  C. Magnard, P. Milillo, S. Oveisgharan, B. '
    'Osmanoglu, P. Rosen, and U. Wegmuller. 2022. Global seasonal Sentinel-1 interferometric coherence and '
    'backscatter data set., Scientific Data. https://doi.org/10.1038/s41597-022-01189-6'
)

DESCRIPTION = (
    'This data set is the first-of-its-kind spatial representation of multi-seasonal, global C-band '
    'Synthetic Aperture Radar (SAR) interferometric repeat-pass coherence and backscatter signatures. Coverage '
    'comprises land masses and ice sheets from 82° Northern to 79° Southern latitudes. The data set is derived from '
    'multi-temporal repeat-pass interferometric processing of about 205,000 Sentinel-1 C-band SAR images acquired in '
    'Interferometric Wide-Swath Mode from 1-Dec-2019 to 30-Nov-2020. The data set encompasses three sets of seasonal '
    '(December-February, March-May, June-August, September-November) metrics produced with a pixel spacing of three '
    'arcseconds: 1) Median 6-, 12-, 18-, 24-, 36-, and 48-days repeat-pass coherence at VV or HH polarizations, 2) '
    'Mean radiometrically terrain corrected backscatter (γ0) at VV and VH, or HH and HV polarizations, and 3) '
    'Estimated parameters of an exponential coherence decay model. The data set has been produced to obtain global, '
    'spatially detailed information on how decorrelation affects interferometric measurements of surface displacement '
    'and is rich in spatial and temporal information for a variety of mapping applications.'
)


def construct_url(s3_client, bucket, key):
    location = s3_client.get_bucket_location(Bucket=bucket)['LocationConstraint']
    url = f'https://{bucket}.s3.{location}.amazonaws.com/{key}'
    return url


def get_object_urls(s3_client, bucket, prefix, requester_pays=False):
    kwargs = {'RequestPayer': 'requester'} if requester_pays else {}
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, **kwargs)
    keys = [x['Key'] for x in response['Contents']]
    urls = [construct_url(s3_client, bucket, x) for x in keys]
    return urls


# TODO why is there an extra zero in N48W090, will this cause issues?
def tileid_to_bbox(tileid):
    north = int(tileid[1:3])
    if tileid[0] == 'S':
        north *= -1
    south = north - 1

    west = int(tileid[4:7])
    if tileid[3] == 'W':
        west *= -1
    east = west + 1
    bbox = geometry.box(west, south, east, north)
    return bbox


def parse_url(url):
    parts = Path(url.upper()).stem.split('_')
    if len(parts) == 3:
        tileid, orbit, product = parts
        bbox = tileid_to_bbox(tileid)
        metadata = {'url': url, 'bbox': bbox, 'tileid': tileid, 'product': product}
        return metadata

    tileid, season, polarization, product = parts
    bbox = tileid_to_bbox(tileid)
    date_range = SEASONS[season]
    metadata = {
        'url': url,
        'bbox': bbox,
        'tileid': tileid,
        'product': product,
        'date_range': date_range,
        'season': season,
        'polarization': polarization,
    }
    return metadata


def create_stac_item(yearly_assets, seasonal_assets):
    ex_asset = seasonal_assets[0]
    item_id = f'{ex_asset["tileid"]}_{ex_asset["season"]}'
    start_date = ex_asset['date_range'][0]
    end_date = ex_asset['date_range'][1]
    mid_date = start_date + (end_date - start_date) / 2
    polarizations = list(set([x['polarization'].upper() for x in seasonal_assets]))
    properties = {
        'tileid': ex_asset['tileid'],
        'season': ex_asset['season'],
        'start_datetime': start_date.isoformat(),
        'end_datetime': end_date.isoformat(),
    }
    item = pystac.Item(
        id=item_id,
        geometry=geometry.mapping(ex_asset['bbox']),
        bbox=ex_asset['bbox'].bounds,
        datetime=mid_date,
        properties=properties,
    )

    ext_sar = sar.SarExtension.ext(item, add_if_missing=True)
    ext_sar.apply(
        'IW',
        sar.FrequencyBand('C'),
        [sar.Polarization(x) for x in polarizations],
        'COH',
        SENTINEL1_CENTER_FREQUENCY,
        looks_range=12,
        looks_azimuth=3,
        observation_direction=sar.ObservationDirection('right'),
    )

    for asset in yearly_assets:
        item.add_asset(
            key=asset['product'],
            asset=pystac.Asset(href=asset['url'], media_type=pystac.MediaType.GEOTIFF),
        )

    for asset in seasonal_assets:
        key = f'{asset["product"]}_{asset["polarization"]}'
        asset_properties = {'polarization': asset['polarization']}
        if 'COH' in asset['product']:
            asset_properties['product'] = 'COH'
            asset_properties['temporal_separation'] = f'{int(asset["product"][-2:])} days'
        else:
            asset_properties['product'] = asset['product']

        item.add_asset(
            key=key,
            asset=pystac.Asset(href=asset['url'], media_type=pystac.MediaType.GEOTIFF, extra_fields=asset_properties),
        )
    return item


def create_tile_stac_collection(
    s3_client, bucket, prefix, date_interval=(datetime(2019, 12, 1), datetime(2020, 11, 30))
):
    urls = get_object_urls(s3_client, bucket, prefix, requester_pays=True)
    asset_dicts = [parse_url(x) for x in urls]
    items = []

    yearly_assets = [x for x in asset_dicts if ('inc' in x['url']) or ('lsmap' in x['url'])]
    seasons = [x['season'] for x in asset_dicts if not (('inc' in x['url']) or ('lsmap' in x['url']))]
    seasons = list(set(seasons))
    for season in seasons:
        seasonal_assets = [x for x in asset_dicts if season.lower() in x['url']]
        item = create_stac_item(yearly_assets, seasonal_assets)
        items.append(item)

    tileid = asset_dicts[0]['tileid']
    spatial_extent = pystac.SpatialExtent(items[0].bbox)
    temporal_extent = pystac.TemporalExtent(intervals=[date_interval])
    collection_extent = pystac.Extent(spatial=spatial_extent, temporal=temporal_extent)
    collection = pystac.Collection(
        id=tileid,
        description=f'Sentinel-1 Coherence Tile {tileid}',
        extent=collection_extent,
    )
    collection.add_items(items)
    return collection


def safe_create_tile_stac_collection(s3_client, bucket, prefix):
    try:
        collection = create_tile_stac_collection(s3_client, bucket, prefix)
    except:
        collection = prefix
    return collection


def create_stac_catalog():
    extra_fields = {'License': LICENSE, 'Data Citation': DATA_CITATION, 'Literature Citation': LITERATURE_CITATION}
    catalog = pystac.Catalog(
        id='sentinel-1-global-coherence-earthbigdata',
        description=DESCRIPTION,
        catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED,
        extra_fields=extra_fields,
    )
    return catalog


def save_stac_catalog_locally(catalog, catalog_name: str):
    catalog_name = Path(catalog_name)
    if not catalog_name.exists():
        catalog_name.mkdir()
    catalog.normalize_hrefs(str(catalog_name))
    catalog.save()
    return catalog_name / 'catalog.json'


def save_stac_catalog_s3(catalog, s3_client, bucket, key):
    base_url = Path(construct_url(s3_client, bucket, key))
    catalog_name = base_url.name
    catalog.normalize_hrefs(str(base_url))
    catalog.save(dest_href=catalog_name)
    return catalog_name


def parse_france_list(data_path):
    with open(data_path, 'r') as f:
        urls = [x.strip() for x in f.readlines()]
    tileids = [parse_url(x)['tileid'] for x in urls]
    return list(set(tileids))


def get_all_tiles(s3_client, bucket, prefix, requester_pays=False):
    kwargs = {'RequestPayer': 'requester'} if requester_pays else {}
    kwargs['Bucket'] = bucket
    kwargs['Prefix'] = prefix
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(**kwargs)
    prefix_lists = []
    for page in page_iterator:
        keys = [x['Key'] for x in page['Contents']]
        page_prefixes = [x.split('/')[2] for x in keys if '.' not in x.split('/')[2]]
        page_prefixes = list(set(page_prefixes))
        prefix_lists.append(page_prefixes)

    prefixes = [item for sublist in prefix_lists for item in sublist]
    prefixes = list(set(prefixes))
    with open('prefixes.txt', 'w') as f:
        f.writelines([x+'\n' for x in prefixes])
    return prefixes


def _update_child(child, catalog_root, catalog_parent_link, catalog_href):
    import pystac
    from pystac.layout import BestPracticesLayoutStrategy

    strategy = BestPracticesLayoutStrategy()

    child.set_root(catalog_root)
    child.remove_links(pystac.RelType.PARENT)
    child.add_link(catalog_parent_link)
    if catalog_href:
        child_href = strategy.get_href(child, os.path.dirname(catalog_href))
        child.set_self_href(child_href)

    return child


def parallel_add_children(catalog, children):
    from pystac.link import Link

    catalog_href = catalog.get_self_href()
    catalog_root = catalog.get_root()
    catalog_parent_link = Link.parent(catalog)

    with ProcessPoolExecutor() as executor:
        children = list(tqdm(executor.map(
            _update_child, children, [catalog_root]*len(children), [catalog_parent_link]*len(children), [catalog_href]*len(children),
        ), total=len(children)))

    links = []
    for child in tqdm(children):
        link = Link.child(child)
        link.set_owner(catalog)
        links.append(link)

    catalog.links.extend(links)

    return catalog


if __name__ == '__main__':
    bucket = 'sentinel-1-global-coherence-earthbigdata'
    upload_bucket = 'ffwilliams2-shenanigans'
    upload_key = 'stac/coherence_stac'

    # tiles = parse_france_list('data/france_urls.txt')
    # prefixes = [f'data/tiles/{x}/' for x in tiles]

    s3 = boto3.client('s3')
    # tiles = get_all_tiles(s3, bucket, 'data/tiles/')
    with open('data/prefixes.txt', 'r') as f:
        tiles = [x.strip() for x in f.readlines()]
    prefixes = [f'data/tiles/{x}/' for x in tiles]

    # Multi-thread
    print('creating items...')
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(
            tqdm(executor.map(safe_create_tile_stac_collection, repeat(s3), repeat(bucket), prefixes), total=len(prefixes))
        )
    
    print('creating catalog...')
    invalid_tiles = []
    catalog = create_stac_catalog()
    for result in results:
        if isinstance(result, pystac.collection.Collection):
            catalog.add_child(result)
        else:
            invalid_tiles.append(result)


    print('saving catalog...')
    catalog_name = save_stac_catalog_locally(catalog, 'coherence_stac')
    with open('data/invalid_tiles.txt', 'w') as f:
        f.writelines([x+'\n' for x in invalid_tiles])
