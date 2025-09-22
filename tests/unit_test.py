import unittest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_package"))

from lambda_function import lambda_handler, parse_vat_number, parse_vies_soap_response


class TestLambdaFunction(unittest.TestCase):

    def test_parse_vat_number_valid(self):
        """Test parse_vat_number with valid inputs"""
        test_cases = [
            ("NL123456789B01", ("NL", "123456789B01")),
            ("DE123456789", ("DE", "123456789")),
            ("FR 12 345 678 901", ("FR", "12345678901")),  # with spaces
            ("be0123456789", ("BE", "0123456789")),  # lowercase
        ]

        for input_vat, expected in test_cases:
            with self.subTest(input_vat=input_vat):
                result = parse_vat_number(input_vat)
                self.assertEqual(result, expected)

    def test_parse_vat_number_invalid(self):
        invalid_cases = [
            "",  # empty
            "A",  # too short
            "AB",  # too short
            "   ",  # whitespace only
        ]

        for input_vat in invalid_cases:
            with self.subTest(input_vat=input_vat):
                result = parse_vat_number(input_vat)
                self.assertEqual(result, (None, None))

    def test_lambda_handler_missing_vat_number(self):
        event = {"body": json.dumps({})}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("error", body)
        self.assertIn("Missing vatNumber parameter", body["error"])

    def test_lambda_handler_invalid_vat_format(self):
        event = {"body": json.dumps({"vatNumber": "XX"})}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("error", body)
        self.assertIn("Invalid VAT format", body["error"])

    def test_lambda_handler_direct_invocation(self):
        event = {"vatNumber": ""}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("error", body)

    def test_lambda_handler_api_gateway_format(self):
        event = {"body": json.dumps({"vatNumber": "NL123456789B01", "method": "soap"})}

        result = lambda_handler(event, None)

        self.assertIn(result["statusCode"], [200, 502])

        self.assertIn("headers", result)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")

    def test_parse_vies_soap_response_valid(self):
        sample_soap_response = """<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <ns2:checkVatResponse xmlns:ns2="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                    <ns2:countryCode>NL</ns2:countryCode>
                    <ns2:vatNumber>123456789B01</ns2:vatNumber>
                    <ns2:requestDate>2025-01-01</ns2:requestDate>
                    <ns2:valid>true</ns2:valid>
                    <ns2:name>Test Company</ns2:name>
                    <ns2:address>Test Address</ns2:address>
                </ns2:checkVatResponse>
            </soap:Body>
        </soap:Envelope>"""

        result = parse_vies_soap_response(sample_soap_response)

        self.assertEqual(result["countryCode"], "NL")
        self.assertEqual(result["vatNumber"], "123456789B01")
        self.assertEqual(result["valid"], True)
        self.assertEqual(result["name"], "Test Company")
        self.assertEqual(result["address"], "Test Address")

    def test_parse_vies_soap_response_fault(self):
        fault_soap_response = """<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <soap:Fault>
                    <faultstring>Invalid country code</faultstring>
                </soap:Fault>
            </soap:Body>
        </soap:Envelope>"""

        result = parse_vies_soap_response(fault_soap_response)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "SOAP Fault")
        self.assertEqual(result["message"], "Invalid country code")

    def test_parse_vies_soap_response_invalid_xml(self):
        invalid_xml = "This is not valid XML"

        result = parse_vies_soap_response(invalid_xml)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "XML Parse Error")

    def test_lambda_handler_json_parse_error(self):
        event = {"body": "invalid json"}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 500)
        body = json.loads(result["body"])
        self.assertIn("error", body)


class TestVATValidation(unittest.TestCase):

    def test_country_code_extraction(self):
        test_cases = [
            ("NL123456789B01", "NL"),
            ("DE123456789", "DE"),
            ("FR12345678901", "FR"),
            ("AT123456789", "AT"),
        ]

        for vat_number, expected_country in test_cases:
            with self.subTest(vat_number=vat_number):
                country_code, _ = parse_vat_number(vat_number)
                self.assertEqual(country_code, expected_country)

    def test_number_extraction(self):
        test_cases = [
            ("NL123456789B01", "123456789B01"),
            ("DE123456789", "123456789"),
            ("FR12345678901", "12345678901"),
        ]

        for vat_number, expected_number in test_cases:
            with self.subTest(vat_number=vat_number):
                _, number = parse_vat_number(vat_number)
                self.assertEqual(number, expected_number)


def run_unit_tests():
    print("Running Lambda Unit Tests...")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestLambdaFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestVATValidation))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"Unit Tests Complete: {result.testsRun} tests run")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)
