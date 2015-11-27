
import time
import os
from collections import defaultdict
op = os.path

import numpy as num

from pyrocko import trace, util, pz, io_common
from pyrocko.fdsn import station as fs
from pyrocko.guts import Object, Tuple, String, Timestamp, Float


class EnhancedSacPzError(io_common.FileLoadError):
    pass


class EnhancedSacPzResponse(Object):
    codes = Tuple.T(4, String.T())
    tmin = Timestamp.T(optional=True)
    tmax = Timestamp.T(optional=True)
    lat = Float.T()
    lon = Float.T()
    elevation = Float.T()
    depth = Float.T()
    dip = Float.T()
    azimuth = Float.T()
    input_unit = String.T()
    output_unit = String.T()
    response = trace.PoleZeroResponse.T()

    def spans(self, *args):
        if len(args) == 0:
            return True
        elif len(args) == 1:
            return ((self.tmin is None or
                     self.tmin <= args[0]) and
                    (self.tmax is None or
                     args[0] <= self.tmax))

        elif len(args) == 2:
            return ((self.tmin is None or
                     args[1] >= self.tmin) and
                    (self.tmax is None or
                     self.tmax >= args[0]))


def make_stationxml_response(presponse, input_unit, output_unit):
    norm_factor = 1.0/float(abs(
        presponse.evaluate(num.array([1.0]))[0]/presponse.constant))

    pzs = fs.PolesZeros(
        pz_transfer_function_type='LAPLACE (RADIANS/SECOND)',
        normalization_factor=norm_factor,
        normalization_frequency=fs.Frequency(1.0),
        zero_list=[fs.PoleZero(real=fs.FloatNoUnit(z.real),
                               imaginary=fs.FloatNoUnit(z.imag))
                   for z in presponse.zeros],
        pole_list=[fs.PoleZero(real=fs.FloatNoUnit(z.real),
                               imaginary=fs.FloatNoUnit(z.imag))
                   for z in presponse.poles])

    pzs.validate()

    stage = fs.ResponseStage(
        number=1,
        poles_zeros_list=[pzs],
        stage_gain=fs.Gain(presponse.constant/norm_factor))

    resp = fs.Response(
        instrument_sensitivity=fs.Sensitivity(
            value=stage.stage_gain.value,
            input_units=fs.Units(input_unit),
            output_units=fs.Units(output_unit)),

        stage_list=[stage])

    return resp


this_year = time.gmtime()[0]


def dummy_aware_str_to_time(s):
    try:
        util.str_to_time(s, format='%Y-%m-%dT%H:%M:%S')
    except util.TimeStrError:
        year = int(s[:4])
        if year > this_year + 100:
            return None  # StationXML contained a dummy end date

        raise


def iload_fh(f):
    zeros, poles, constant, comments = pz.read_sac_zpk(file=f,
                                                       get_comments=True)
    d = {}
    for line in comments:
        toks = line.split(':', 1)
        if len(toks) == 2:
            temp = toks[0].strip('* \t')
            for k in ('network', 'station', 'location', 'channel', 'start',
                      'end', 'latitude', 'longitude', 'depth', 'elevation',
                      'dip', 'azimuth', 'input unit', 'output unit'):

                if temp.lower().startswith(k):
                    d[k] = toks[1].strip()

    response = trace.PoleZeroResponse(zeros, poles, constant)

    try:
        yield EnhancedSacPzResponse(
            codes=(d['network'], d['station'], d['location'], d['channel']),
            tmin=util.str_to_time(d['start'], format='%Y-%m-%dT%H:%M:%S'),
            tmax=dummy_aware_str_to_time(d['end']),
            lat=float(d['latitude']),
            lon=float(d['longitude']),
            elevation=float(d['elevation']),
            depth=float(d['depth']),
            dip=float(d['dip']),
            azimuth=float(d['azimuth']),
            input_unit=d['input unit'],
            output_unit=d['output unit'],
            response=response)
    except:
        raise EnhancedSacPzError('cannot get all required information')


iload_filename, iload_dirname, iload_glob, iload = util.make_iload_family(
    iload_fh, 'SACPZ', ':py:class:`EnhancedSacPzResponse`')


def make_stationxml(responses, inconsistencies='warn'):
    '''
    Create stationxml from "enhanced" SACPZ information.

    :param responses: iterable yielding
        :py:class:`EnhancedSacPzResponse` objects
    :returns: :py:class:`pyrocko.fdsn.station.FDSNStationXML` object
    '''

    networks = {}
    stations = {}

    station_coords = defaultdict(list)
    station_channels = defaultdict(list)
    for cr in responses:
        net, sta, loc, cha = cr.codes
        station_coords[net, sta].append(
            (cr.codes, cr.lat, cr.lon, cr.elevation))

        station_channels[net, sta].append(fs.Channel(
            code=cha,
            location_code=loc,
            start_date=cr.tmin,
            end_date=cr.tmax,
            latitude=fs.Latitude(cr.lat),
            longitude=fs.Longitude(cr.lon),
            elevation=fs.Distance(cr.elevation),
            depth=fs.Distance(cr.depth),
            response=make_stationxml_response(
                cr.response, cr.input_unit, cr.output_unit)))

    for (net, sta), v in sorted(station_coords.iteritems()):
        lat, lon, elevation = util.consistency_merge(
            v,
            message='channel lat/lon/elevation values differ',
            error=inconsistencies)

        if net not in networks:
            networks[net] = fs.Network(code=net)

        stations[net, sta] = fs.Station(
            code=sta,
            latitude=fs.Latitude(lat),
            longitude=fs.Longitude(lon),
            elevation=fs.Distance(elevation),
            channel_list=sorted(
                station_channels[net, sta],
                key=lambda c: (c.location_code, c.code)))

        networks[net].station_list.append(stations[net, sta])

    return fs.FDSNStationXML(
        source='Converted from "enhanced" SACPZ information',
        created=time.time(),
        network_list=[networks[net_] for net_ in sorted(networks.keys())])

if __name__ == '__main__':

    import sys

    util.setup_logging(__name__)

    if len(sys.argv) < 2:
        sys.exit('usage: python -m pyrocko.station.enhanced_sacpz <sacpz> ...')

    sxml = make_stationxml(iload(sys.argv[1:]))
    print sxml.dump_xml()