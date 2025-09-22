import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    AWS Lambda handler for EU VIES VAT number checking

    Expected event format:
    {
        "vatNumber": "DE129274202",
        "method": "soap"  // optional: "soap" or "rest", defaults to "soap"
    }
    """

    try:
        vat_input = event.get("vatNumber")
        if not vat_input:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": "Missing vatNumber parameter",
                        "message": "Please provide a vatNumber in the request body",
                    }
                ),
            }

        country_code, vat_number = parse_vat_number(vat_input)

        if not country_code or not vat_number:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": "Invalid VAT format",
                        "message": "VAT number must include country code (e.g., DE129274202)",
                    }
                ),
            }

        method = event.get("method", "soap").lower()

        logger.info(f"Checking VAT {country_code}{vat_number} via {method}")

        if method == "rest":
            result = check_vat_vies_rest(country_code, vat_number)
        else:
            result = check_vat_vies_soap(country_code, vat_number)

        if "error" in result:
            return {
                "statusCode": 502,
                "body": json.dumps(
                    {
                        "error": "VIES Service Error",
                        "details": result,
                        "vatNumber": f"{country_code}{vat_number}",
                        "method": method,
                    }
                ),
            }

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "success": True,
                    "data": result,
                    "vatNumber": f"{country_code}{vat_number}",
                    "method": method,
                },
                ensure_ascii=False,
            ),
        }

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }


def parse_vat_number(vat_number):
    vat_number = vat_number.strip().replace(" ", "").upper()

    if len(vat_number) < 3:
        return None, None

    country_code = vat_number[:2]
    number = vat_number[2:]

    return country_code, number


def check_vat_vies_soap(country_code, vat_number):
    soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types"
                xmlns:impl="urn:ec.europa.eu:taxud:vies:services:checkVat">
        <soap:Header>
        </soap:Header>
        <soap:Body>
            <tns1:checkVat xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types"
                        xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                <tns1:countryCode>{country_code}</tns1:countryCode>
                <tns1:vatNumber>{vat_number}</tns1:vatNumber>
            </tns1:checkVat>
        </soap:Body>
    </soap:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "urn:ec.europa.eu:taxud:vies:services:checkVat/checkVat",
        "User-Agent": "AWS-Lambda-VAT-Checker/1.0",
    }

    url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"

    try:
        logger.info(f"Making SOAP request to VIES for {country_code}{vat_number}")
        response = requests.post(url, data=soap_envelope, headers=headers, timeout=10)

        if response.status_code == 200:
            return parse_vies_soap_response(response.text)
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "message": response.text[:200],
            }

    except requests.RequestException as e:
        logger.error(f"SOAP request error: {str(e)}")
        return {"error": "Network error", "message": str(e)}
    except Exception as e:
        logger.error(f"SOAP parsing error: {str(e)}")
        return {"error": "Parsing error", "message": str(e)}


def check_vat_vies_rest(country_code, vat_number):
    """unofficial rest api -> sometimes available"""
    url = f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country_code}/vat/{quote(vat_number)}"

    headers = {"Accept": "application/json", "User-Agent": "AWS-Lambda-VAT-Checker/1.0"}

    try:
        logger.info(f"Making REST request to VIES for {country_code}{vat_number}")
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "message": response.text[:200],
            }

    except requests.RequestException as e:
        logger.error(f"REST request error: {str(e)}")
        return {"error": "Network error", "message": str(e)}
    except Exception as e:
        logger.error(f"REST parsing error: {str(e)}")
        return {"error": "Parsing error", "message": str(e)}


def parse_vies_soap_response(xml_response):
    try:
        root = ET.fromstring(xml_response)

        namespaces = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "ns2": "urn:ec.europa.eu:taxud:vies:services:checkVat:types",
        }

        fault = root.find(".//soap:Fault", namespaces)
        if fault is not None:
            fault_string = fault.find("faultstring")
            return {
                "error": "SOAP Fault",
                "message": (
                    fault_string.text
                    if fault_string is not None
                    else "Unknown SOAP fault"
                ),
            }

        response_elem = root.find(".//ns2:checkVatResponse", namespaces)
        if response_elem is None:
            return {"error": "Invalid response", "message": "No checkVatResponse found"}

        def get_text(elem_name):
            elem = response_elem.find(f"ns2:{elem_name}", namespaces)
            return elem.text if elem is not None else None

        return {
            "countryCode": get_text("countryCode"),
            "vatNumber": get_text("vatNumber"),
            "requestDate": get_text("requestDate"),
            "valid": get_text("valid") == "true",
            "name": get_text("name"),
            "address": get_text("address"),
        }

    except ET.ParseError as e:
        logger.error(f"XML parse error: {str(e)}")
        return {"error": "XML Parse Error", "message": str(e)}
    except Exception as e:
        logger.error(f"Response parse error: {str(e)}")
        return {"error": "Response Parse Error", "message": str(e)}

def test_lambda_locally():
    """Test function for local development"""
    # test_event = {
    # "vatNumber": "DE129274202",
    # "method": "soap"
    # }

    test_events = [
        {"vatNumber": "NL123456789B01", "method": "soap"},  # Netherlands
        {"vatNumber": "BE0123456789", "method": "soap"},  # Belgium
        {"vatNumber": "FR12345678901", "method": "soap"},  # France
    ]

    for event in test_events:
        result = lambda_handler(event, None)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_lambda_locally()
