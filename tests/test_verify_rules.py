"""Stage A verifier rules against a local stub HTTP server (spec 001, R5)."""

import unittest

from helpers import StubServer, response, verify

HELLO_JSON = '{"message":"Hello, World!"}'
URLS = {"json_url": "/json", "plaintext_url": "/plaintext"}


def ok_json(**kw):
    return lambda: response(HELLO_JSON, **kw)


def ok_text(body="Hello, World!", **kw):
    kw.setdefault("content_type", "text/plain")
    return lambda: response(body, **kw)


class RulesTestCase(unittest.TestCase):
    def run_variant(self, routes, urls=None):
        with StubServer(routes) as srv:
            return verify.verify_variant(srv.url, urls or URLS, "A", date_delay=0)

    def assertStatus(self, result, test_type, status, needle=None):
        res = result[test_type]
        self.assertEqual(res["status"], status, res["findings"])
        if needle:
            self.assertTrue(any(needle in f["message"] for f in res["findings"]),
                            res["findings"])


class PassTest(RulesTestCase):
    def test_json_and_plaintext_pass(self):
        r = self.run_variant({"/json": ok_json(), "/plaintext": ok_text()})
        self.assertStatus(r, "json", "pass")
        self.assertStatus(r, "plaintext", "pass")
        self.assertEqual(r["json"]["findings"], [])

    def test_charset_and_case_insensitive_values(self):
        r = self.run_variant({
            "/json": lambda: response('{"Message": "hello, WORLD!"}',
                                      content_type="application/json; charset=utf-8"),
            "/plaintext": ok_text("HELLO, world!", content_type="text/plain;charset=UTF-8"),
        })
        self.assertStatus(r, "json", "pass")
        self.assertStatus(r, "plaintext", "pass")

    def test_chunked_transfer_encoding_is_a_size_header(self):
        def chunked():
            status, headers, body = response("Hello, World!", content_type="text/plain",
                                             Content_Length=None, Transfer_Encoding="chunked")
            return status, headers, b"d\r\nHello, World!\r\n0\r\n\r\n"
        r = self.run_variant({"/plaintext": chunked}, {"plaintext_url": "/plaintext"})
        self.assertStatus(r, "plaintext", "pass")


class WarnTest(RulesTestCase):
    def test_json_extra_keys_warn(self):
        r = self.run_variant({"/json": lambda: response('{"message":"Hello, World!","x":"y"}')},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "warn", "Extra JSON keys")

    def test_plaintext_extra_bytes_warn(self):
        r = self.run_variant({"/plaintext": ok_text("Hello, World!\n")},
                             {"plaintext_url": "/plaintext"})
        self.assertStatus(r, "plaintext", "warn", "1 byte(s) more")

    def test_bad_date_format_warns(self):
        dates = iter(["2024-01-01 00:00:%02d" % i for i in range(10)])
        r = self.run_variant({"/json": ok_json(Date=lambda: next(dates))}, {"json_url": "/json"})
        self.assertStatus(r, "json", "warn", "IMF-fixdate")


class FailTest(RulesTestCase):
    def test_wrong_message_fails(self):
        r = self.run_variant({"/json": lambda: response('{"message":"Goodbye"}')},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "Expected message")

    def test_json_array_fails(self):
        r = self.run_variant({"/json": lambda: response('[{"message":"Hello, World!"}]')},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "not a JSON object")

    def test_missing_message_key_fails(self):
        r = self.run_variant({"/json": lambda: response('{"msg":"Hello, World!"}')},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "Missing required key")

    def test_invalid_json_fails(self):
        r = self.run_variant({"/json": lambda: response("Hello, World!")}, {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "Invalid JSON")

    def test_empty_body_fails(self):
        r = self.run_variant({"/json": lambda: response("")}, {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "Empty response body")

    def test_plaintext_without_hello_fails(self):
        r = self.run_variant({"/plaintext": ok_text("Bye")}, {"plaintext_url": "/plaintext"})
        self.assertStatus(r, "plaintext", "fail", "does not contain")

    def test_wrong_status_fails(self):
        r = self.run_variant({"/json": lambda: response(HELLO_JSON, status=201)},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "HTTP status 201")

    def test_error_status_with_valid_body_fails(self):
        r = self.run_variant({"/json": lambda: response(HELLO_JSON, status=500)},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "HTTP status 500")

    def test_missing_required_headers_fail(self):
        for header in ("Server", "Date", "Content-Type"):
            with self.subTest(header=header):
                r = self.run_variant({"/json": ok_json(**{header.replace("-", "_"): None})},
                                     {"json_url": "/json"})
                self.assertStatus(r, "json", "fail", "header missing: %s" % header)

    def test_missing_size_header_fails(self):
        r = self.run_variant({"/json": ok_json(Content_Length=None)}, {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "Content-Length or Transfer-Encoding")

    def test_cached_date_fails(self):
        r = self.run_variant({"/json": ok_json(Date="Mon, 01 Jan 2024 00:00:00 GMT")},
                             {"json_url": "/json"})
        self.assertStatus(r, "json", "fail", "cached")

    def test_wrong_content_type_fails(self):
        r = self.run_variant({
            "/json": ok_json(content_type="text/plain"),
            "/plaintext": ok_text(content_type="text/html"),
        })
        self.assertStatus(r, "json", "fail", "Content-Type 'text/plain'")
        self.assertStatus(r, "plaintext", "fail", "Content-Type 'text/html'")

    def test_short_route_fails(self):
        r = self.run_variant({"/j": ok_json(), "/plain": ok_text()},
                             {"json_url": "/j", "plaintext_url": "/plain"})
        self.assertStatus(r, "json", "fail", "at least 5 characters")
        self.assertStatus(r, "plaintext", "fail", "at least 10 characters")

    def test_no_server_fails(self):
        r = verify.verify_variant("http://127.0.0.1:9", {"json_url": "/json"}, "A", date_delay=0)
        self.assertStatus(r, "json", "fail", "No response")


class StageTest(RulesTestCase):
    def test_later_stage_types_are_declared_not_verified(self):
        urls = dict(URLS, db_url="/db", query_url="/queries?q=", cached_query_url="/cached?q=")
        r = self.run_variant({"/json": ok_json(), "/plaintext": ok_text()}, urls)
        self.assertEqual(list(r), ["json", "plaintext", "db", "query", "cached-query"])
        for t in ("db", "query", "cached-query"):
            self.assertEqual(r[t]["status"], verify.NOT_VERIFIED)

    def test_unimplemented_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            verify.verify_variant("http://127.0.0.1:9", URLS, "B")


if __name__ == "__main__":
    unittest.main()
