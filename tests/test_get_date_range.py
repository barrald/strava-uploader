#!/usr/bin/env python

import unittest
from datetime import datetime, date
from uploader import get_date_range

class TestGetDateRange(unittest.TestCase):

    def test_get_date_range_requires_datetime(self):
		with self.assertRaises(TypeError):
			get_date_range('a')
		with self.assertRaises(TypeError):
			get_date_range(12)

    def test_get_date_range_default(self):
		source = datetime(2005, 7, 14, 12, 30, 45)
		expectedFrom = datetime(2005, 7, 14, 0, 30, 45)
		expectedTo = datetime(2005, 7, 15, 0, 30, 45)
		expected = { 'from': expectedFrom, 'to': expectedTo }

		res = get_date_range(source)
		self.assertEqual(res, expected)

    def test_get_date_range(self):
		source = datetime(2005, 7, 14, 12, 30, 45)
		expectedFrom = datetime(2005, 7, 13, 12, 30, 45)
		expectedTo = datetime(2005, 7, 15, 12, 30, 45)
		expected = { 'from': expectedFrom, 'to': expectedTo }

		res = get_date_range(source, 24)
		self.assertEqual(res, expected)
