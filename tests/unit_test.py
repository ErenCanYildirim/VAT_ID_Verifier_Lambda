import unittest
import json
from unittest.mock import patch, Mock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from lambda_function import (
        lambda_handler,
        parse_vat_number,
        check_vat_vies_soap,
        check_vat_vies_rest,
        parse_vies_soap_response,
    )
except ImportError:
    import lambda_function

    lambda_handler = lambda_function.lambda_handler
    parse_vat_number = lambda_function.parse_vat_number
    check_vat_vies_soap = lambda_function.check_vat_vies_soap
    check_vat_vies_rest = lambda_function.check_vat_vies_rest
    parse_vies_soap_response = lambda_function.parse_vies_soap_response


class TestVATChecker(unittest.TestCase):

    def test_parse_vat_number_valid(self):
        # Test standard format
        country, number = parse_vat_number("DE129274202")
        self.assertEqual(country, "DE")
        self.assertEqual(number, "129274202")

        # Test with spaces
        country, number = parse_vat_number("DE 123 456 789")
        self.assertEqual(country, "DE")
        self.assertEqual(number, "123456789")

        # Test lowercase
        country, number = parse_vat_number("de129274202")
        self.assertEqual(country, "DE")
        self.assertEqual(number, "129274202")

    def test_parse_vat_number_invalid(self):
        # Too short
        country, number = parse_vat_number("DE")
        self.assertIsNone(country)
        self.assertIsNone(number)

        # Empty
        country, number = parse_vat_number("")
        self.assertIsNone(country)
        self.assertIsNone(number)

        # Single character
        country, number = parse_vat_number("D")
        self.assertIsNone(country)
        self.assertIsNone(number)

    def test_lambda_handler_missing_vat(self):
        event = {}
        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Missing vatNumber parameter")

    def test_lambda_handler_invalid_vat_format(self):
        event = {"vatNumber": "DE"}
        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Invalid VAT format")

    @patch("lambda_function.requests.post")
    def test_soap_request_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <ns2:checkVatResponse xmlns:ns2="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                    <ns2:countryCode>DE</ns2:countryCode>
                    <ns2:vatNumber>129274202</ns2:vatNumber>
                    <ns2:requestDate>2025-09-22</ns2:requestDate>
                    <ns2:valid>true</ns2:valid>
                    <ns2:name>Test Company</ns2:name>
                    <ns2:address>Test Address</ns2:address>
                </ns2:checkVatResponse>
            </soap:Body>
        </soap:Envelope>"""
        mock_post.return_value = mock_response

        result = check_vat_vies_soap("DE", "129274202")

        self.assertEqual(result["countryCode"], "DE")
        self.assertEqual(result["vatNumber"], "129274202")
        self.assertTrue(result["valid"])
        self.assertEqual(result["name"], "Test Company")

    @patch("lambda_function.requests.post")
    def test_soap_request_network_error(self, mock_post):
        mock_post.side_effect = Exception("Connection timeout")
        result = check_vat_vies_soap("DE", "129274202")

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Parsing error")

    @patch("lambda_function.requests.get")
    def test_rest_request_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "countryCode": "DE",
            "vatNumber": "129274202",
            "valid": True,
            "name": "Test Company",
        }
        mock_get.return_value = mock_response

        result = check_vat_vies_rest("DE", "129274202")

        self.assertEqual(result["countryCode"], "DE")
        self.assertTrue(result["valid"])

    @patch("lambda_function.requests.get")
    def test_rest_request_http_error(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        result = check_vat_vies_rest("DE", "129274202")

        self.assertIn("error", result)
        self.assertEqual(result["error"], "HTTP 404")

    def test_parse_soap_response_valid(self):
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <ns2:checkVatResponse xmlns:ns2="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                    <ns2:countryCode>DE</ns2:countryCode>
                    <ns2:vatNumber>129274202</ns2:vatNumber>
                    <ns2:requestDate>2025-09-22</ns2:requestDate>
                    <ns2:valid>true</ns2:valid>
                    <ns2:name>Test Company</ns2:name>
                    <ns2:address>Test Address</ns2:address>
                </ns2:checkVatResponse>
            </soap:Body>
        </soap:Envelope>"""

        result = parse_vies_soap_response(xml_response)

        self.assertEqual(result["countryCode"], "DE")
        self.assertEqual(result["vatNumber"], "129274202")
        self.assertTrue(result["valid"])
        self.assertEqual(result["name"], "Test Company")

    def test_parse_soap_response_fault(self):
        """Test parsing SOAP fault response"""
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <soap:Fault>
                    <faultstring>Invalid country code</faultstring>
                </soap:Fault>
            </soap:Body>
        </soap:Envelope>"""

        result = parse_vies_soap_response(xml_response)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "SOAP Fault")
        self.assertEqual(result["message"], "Invalid country code")

    def test_parse_soap_response_invalid_xml(self):
        xml_response = "Not valid XML"
        result = parse_vies_soap_response(xml_response)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "XML Parse Error")

    @patch("lambda_function.check_vat_vies_soap")
    def test_lambda_handler_success(self, mock_soap):
        mock_soap.return_value = {
            "countryCode": "DE",
            "vatNumber": "129274202",
            "requestDate": "2025-09-22",
            "valid": True,
            "name": "Test Company",
            "address": "Test Address",
        }

        event = {"vatNumber": "DE129274202", "method": "soap"}

        response = lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertTrue(body["success"])
        self.assertTrue(body["data"]["valid"])
        self.assertEqual(body["vatNumber"], "DE129274202")

    @patch("lambda_function.check_vat_vies_soap")
    def test_lambda_handler_vies_error(self, mock_soap):
        mock_soap.return_value = {
            "error": "Network error",
            "message": "Connection timeout",
        }

        event = {"vatNumber": "DE129274202", "method": "soap"}

        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 502)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "VIES Service Error")

    def test_lambda_handler_exception(self):
        event = None

        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Internal server error")

    def test_method_selection(self):
        with patch("lambda_function.check_vat_vies_rest") as mock_rest:
            mock_rest.return_value = {"valid": True, "countryCode": "DE"}

            event = {"vatNumber": "DE129274202", "method": "rest"}

            lambda_handler(event, None)
            mock_rest.assert_called_once_with("DE", "129274202")

class TestVATCheckerIntegration(unittest.TestCase):

    def setUp(self):
        """skip integration tests if no network access is there"""
        try:
            import requests
            requests.get('https://www.google.com', timeout=5)
        except:
            self.skipTest("No network access available")

    def test_invalid_vat_number_integration(self):
        """test with obviously invalid VAT number"""
        result = check_vat_vies_soap("XX", "123456789")

        self.assertTrue('error' in result or result.get('valid') == False)



if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestVATChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestVATCheckerIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)