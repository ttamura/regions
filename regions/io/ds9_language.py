import string
import itertools
import re
from astropy import units as u
from astropy import coordinates

def coordinate(string_rep, unit):
    # Any ds9 coordinate representation (sexagesimal or degrees)
    try:
        return coordinates.Angle(string_rep)
    except u.UnitsError:
        if unit == 'hour_or_deg':
            if ':' in string_rep:
                return coordinates.Angle(string_rep, unit=u.hour)
            else:
                return coordinates.Angle(string_rep, unit=u.deg)
        elif unit.is_equivalent(u.deg):
            return coordinates.Angle(string_rep, unit=unit)
        else:
            return u.Quantity(float(string_rep), unit)

unit_mapping = {'"': u.arcsec,
                "'": u.arcmin,
                'r': u.rad,
                'i': u.dimensionless_unscaled,

               }

def angular_length_quantity(string_rep):
    has_unit = string_rep[-1] not in string.digits
    if has_unit:
        unit = unit_mapping[string_rep[-1]]
        return u.Quantity(float(string_rep[:-1]), unit=unit)
    else:
        return u.Quantity(float(string_rep), unit=u.deg)

# these are the same function, just different names
radius = angular_length_quantity
width = angular_length_quantity
height = angular_length_quantity
angle = angular_length_quantity

language_spec = {'point': (coordinate, coordinate),
                 'circle': (coordinate, coordinate, radius),
                 'box': (coordinate, coordinate, width, height, angle),
                 'polygon': itertools.cycle((coordinate, )),
                }

coordinate_systems = ['fk5', 'fk4', 'icrs', 'galactic', 'wcs', 'physical', 'image', 'ecliptic']
coordinate_systems += ['wcs{0}'.format(letter) for letter in string.ascii_lowercase]

coordsys_name_mapping = dict(zip(coordinates.frame_transform_graph.get_names(),
                                 coordinates.frame_transform_graph.get_names()))
coordsys_name_mapping['ecliptic'] = 'geocentrictrueecliptic' # needs expert attention TODO

hour_or_deg = 'hour_or_deg'
coordinate_units = {'fk5': (hour_or_deg, u.deg),
                    'fk4': (hour_or_deg, u.deg),
                    'icrs': (hour_or_deg, u.deg),
                    'geocentrictrueecliptic': (u.deg, u.deg),
                    'galactic': (u.deg, u.deg),
                    'physical': (u.dimensionless_unscaled, u.dimensionless_unscaled),
                    'image': (u.dimensionless_unscaled, u.dimensionless_unscaled),
                    'wcs': (u.dimensionless_unscaled, u.dimensionless_unscaled),
                   }
for letter in string.ascii_lowercase:
    coordinate_units['wcs{0}'.format(letter)] = (u.dimensionless_unscaled, u.dimensionless_unscaled)

# circle(1.5, 3.6, 1.2)

region_type_or_coordsys_re = re.compile("#? *([a-zA-Z0-9]+)")

paren = re.compile("[()]")

def strip_paren(string_rep):
    return paren.sub("", string_rep)

def ds9_parser(filename):
    """
    Parse a complete ds9 .reg file

    Returns
    -------
    list of (region type, coord_list) tuples
    """
    coordsys = None
    regions = []
    composite_region = None

    with open(filename,'r') as fh:
        for line_ in fh:
            # ds9 regions can be split on \n or ;
            for line in line_.split(";"):
                parsed = line_parser(line, coordsys)
                if parsed in coordinate_systems:
                    coordsys = parsed
                elif parsed:
                    region_type, coordlist, composite = parsed
                    if composite and composite_region is None:
                        composite_region = [(region_type, coordlist)]
                    elif composite:
                        composite_region.append((region_type, coordlist))
                    elif composite_region is not None:
                        composite_region.append((region_type, coordlist))
                        regions.append(composite_region)
                        composite_region = None
                    else:
                        regions.append((region_type, coordlist))

    return regions

def line_parser(line, coordsys=None):
    region_type_search = region_type_or_coordsys_re.search(line)
    if region_type_search:
        region_type = region_type_search.groups()[0]
    else:
        return

    if region_type in coordinate_systems:
        return region_type # outer loop has to do something with the coordinate system information
    elif region_type in language_spec:
        if coordsys is None:
            raise ValueError("No coordinate system specified and a region has been found.")

        if "||" in line:
            composite = True
        else:
            composite = False

        # end_of_region_name is the coordinate of the end of the region's name, e.g.:
        # circle would be 6 because circle is 6 characters
        end_of_region_name = region_type_search.span()[1]
        # coordinate of the # symbol or end of the line (-1) if not found
        hash_or_end = line.find("#")
        coords_etc = strip_paren(line[end_of_region_name:hash_or_end].strip(" |"))
        if coordsys in coordsys_name_mapping:
            parsed = type_parser(coords_etc, language_spec[region_type],
                                 coordsys_name_mapping[coordsys])
            coords = coordinates.SkyCoord([(x, y)
                                           for x, y in zip(parsed[:-1:2], parsed[1::2])
                                           if isinstance(x, coordinates.Angle) and
                                           isinstance(x, coordinates.Angle)], frame=coordsys_name_mapping[coordsys])
            return region_type, [coords] + parsed[len(coords)*2:], composite
        else:
            return region_type, type_parser(coords_etc, language_spec[region_type],
                                            coordsys), composite

def type_parser(string_rep, specification, coordsys):
    coord_list = []
    splitter = re.compile("[, ]")
    for ii, (element, element_parser) in enumerate(zip(splitter.split(string_rep), specification)):
        if element_parser is coordinate:
            unit = coordinate_units[coordsys][ii % 2]
            coord_list.append(element_parser(element, unit))
        else:
            coord_list.append(element_parser(element))

    return coord_list

if __name__ == "__main__":
    # simple tests for now...
    import glob
    for fn in glob.glob('/Users/adam/Downloads/tests/regions/*.reg'):
        print(fn)
        ds9_parser(fn)
