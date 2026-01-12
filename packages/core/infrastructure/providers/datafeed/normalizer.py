"""
Data Normalizer

This module provides a simple data normalizer to ensure data consistency from different sources.
"""

from typing import Any, Dict, List


class DataNormalizer:
    """
    A simple data normalizer that can handle different key names for the same data.
    """

    def __init__(self, schema_mapping: Dict[str, str]):
        """
        Initializes the normalizer with a schema mapping.

        Args:
            schema_mapping: A dictionary that maps the desired key names to the original key names.
                            For example: {"open": "open_price", "close": "close_price"}
        """
        self.schema_mapping = schema_mapping
        self.reverse_mapping = {v: k for k, v in schema_mapping.items()}

    def normalize(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalizes a list of data records.

        Args:
            data: A list of dictionaries, where each dictionary is a data record.

        Returns:
            A list of normalized data records.
        """
        normalized_data = []
        for record in data:
            normalized_record = {}
            for key, value in record.items():
                new_key = self.reverse_mapping.get(key, key)
                normalized_record[new_key] = value
            normalized_data.append(normalized_record)
        return normalized_data
