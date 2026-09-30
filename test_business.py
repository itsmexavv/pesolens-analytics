import csv
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from core import APIError, csv_text, money
from app import Peso


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.peso = Peso(Path(self.temp.name)/"test.db")

    def tearDown(self):
        self.temp.cleanup()

    def call(self, app, method, path, data=None, query=None):
        return app.handle(method, path, data or {}, query or {})

    def test_money_exactness_and_invalid_values(self):
        self.assertEqual(money('0.29'), 29)
        self.assertEqual(money('1.10'), 110)
        for invalid in ['NaN', 'Infinity', '-1', '1.001', None, '1000001']:
            with self.subTest(invalid=invalid), self.assertRaises(APIError):
                money(invalid)

    def test_export_neutralizes_spreadsheet_formulas(self):
        value = csv_text(['note'], [[' =HYPERLINK("x")']])
        self.assertTrue(list(csv.reader(io.StringIO(value)))[1][0].startswith("'"))

    def test_expense_summary_is_scoped_to_month(self):
        data = {'kind':'expense','category':'Test','amount':'0.29','date':'2020-01-01','note':'Exact'}
        self.call(self.peso,'POST','/transactions',data)
        summary = self.call(self.peso,'GET','/summary',query={'month':['2020-01']})
        self.assertEqual((summary['income'],summary['expense'],summary['balance']), (0,29,-29))
        self.assertEqual(summary['categories'],[{'category':'Test','total':29}])

    def test_csv_import_is_atomic(self):
        month = date.today().strftime('%Y-%m')
        before = self.call(self.peso,'GET','/transactions',query={'month':[month]})
        source = f'kind,category,amount,date,note\nexpense,Food,10,{month}-01,Valid\nexpense,Food,-5,{month}-01,Invalid\n'
        with self.assertRaises(APIError):
            self.call(self.peso,'POST','/import',{'csv':source})
        self.assertEqual(self.call(self.peso,'GET','/transactions',query={'month':[month]}), before)

    def test_csv_import_quotes_and_export(self):
        source = 'kind,category,amount,date,note\nexpense,Food,12.25,2020-02-01,"Lunch, snack"\n'
        self.assertEqual(self.call(self.peso,'POST','/import',{'csv':source})['imported'],1)
        exported,_ = self.call(self.peso,'GET','/export',query={'month':['2020-02']})
        record = list(csv.DictReader(io.StringIO(exported)))[0]
        self.assertEqual((record['note'],record['amount']),('Lunch, snack','12.25'))

    def test_bad_month_and_missing_transaction(self):
        with self.assertRaises(APIError):
            self.call(self.peso,'GET','/summary',query={'month':['2026-99']})
        with self.assertRaises(APIError):
            self.call(self.peso,'DELETE','/transactions/999')
