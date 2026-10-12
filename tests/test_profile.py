import csv
import json
import tempfile
import unittest
from pathlib import Path
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pawpair.profile import profile, load_catalog


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows(rows)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.processed = self.root / "processed"
        write_csv(self.raw / "aisles.csv", ["aisle_id", "aisle"], [
            [1, "cat food care"], [2, "dog food care"], [3, "milk"]])
        write_csv(self.raw / "products.csv", ["product_id", "product_name", "aisle_id", "department_id"], [
            [10, "Cat Kibble", 1, 18], [11, "Cat Snacks", 1, 18],
            [20, "Dog Treats", 2, 18], [21, "Dog Shampoo", 2, 18], [30, "Regular Milk", 3, 16]])
        write_csv(self.raw / "order_products__train.csv", ["order_id", "product_id", "add_to_cart_order", "reordered"], [
            [100, 10, 1, 0], [100, 11, 2, 0], [100, 30, 3, 0],
            [100, 10, 4, 0],  # duplicate should not inflate count
            [101, 10, 1, 0], [102, 20, 1, 0], [102, 21, 2, 0],
            [103, 30, 1, 0], [104, "", 1, 0]])

    def tearDown(self):
        self.temp.cleanup()

    def test_pet_only_baskets_include_singletons(self):
        stats = profile(self.raw, self.processed)
        self.assertEqual(stats["pet_containing_orders"], 3)
        self.assertEqual(stats["multi_pet_item_orders"], 2)
        self.assertEqual(stats["pet_products_observed"], 4)
        self.assertEqual(stats["pair_types_observed"], 2)
        self.assertEqual(stats["counters"]["duplicate_pet_product_rows"], 1)
        self.assertEqual(stats["counters"]["rows_missing_order_or_product_id"], 1)
        self.assertEqual(stats["counters"]["rows_not_in_pet_aisles"], 2)
        with (self.processed / "pet_baskets.csv").open(encoding="utf-8", newline="") as fp:
            data = list(csv.DictReader(fp))
        self.assertEqual(len(data), 3)
        self.assertEqual(json.loads(data[0]["product_ids_json"]), ["10", "11"])
        self.assertEqual(json.loads(data[1]["product_ids_json"]), ["10"])
        self.assertEqual(stats["most_frequent_pet_pairs"][0]["support"], round(1/3, 8))

    def test_required_pet_aisles(self):
        write_csv(self.raw / "aisles.csv", ["aisle_id", "aisle"], [[1, "cat food care"]])
        with self.assertRaisesRegex(ValueError, "Missing aisles"):
            load_catalog(self.raw, ("cat food care", "dog food care"))

    def test_missing_order_file_fails_cleanly(self):
        (self.raw / "order_products__train.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            profile(self.raw, self.processed)


if __name__ == "__main__":
    unittest.main()
