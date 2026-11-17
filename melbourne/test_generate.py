import unittest
from generate import STATIONS, select_corridor, station_name

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.stations = {str(i): (name + ' Railway Station', 0, 0) for i, name in enumerate(STATIONS)}
        self.stations['loop'] = ('Parliament Railway Station', 0, 0)
        self.routes = {'rail': 'Frankston'}
        self.outbound = ('rail', '0', list(map(str, range(8))), list(range(8)))
        self.inbound = ('rail', '1', list(map(str, range(7, 0, -1))) + ['loop', '0'], list(range(9)))

    def test_selects_contiguous_pieces_and_excludes_loop(self):
        selected = select_corridor(self.stations, [self.outbound, self.inbound], self.routes)
        self.assertEqual(selected[0][2], list(map(str, range(8))))
        self.assertEqual(selected[1][2], list(map(str, range(7, 0, -1))))

    def test_rejects_missing_intermediate_stop(self):
        bad = ('rail', '0', ['0', '1', 'loop'] + list(map(str, range(2, 8))), list(range(9)))
        with self.assertRaises(ValueError): select_corridor(self.stations, [bad, self.inbound], self.routes)

    def test_rejects_one_direction_and_replacement(self):
        with self.assertRaises(ValueError): select_corridor(self.stations, [self.outbound], self.routes)
        with self.assertRaises(ValueError): select_corridor(self.stations, [self.outbound, self.inbound], {'rail': 'Replacement Bus'})

    def test_station_suffix(self):
        self.assertEqual(station_name('South Yarra Railway Station'), 'South Yarra')

if __name__ == '__main__': unittest.main()
