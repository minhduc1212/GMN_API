# Google Gemini Web Protocol Reverse Engineering Guide

This document explains the communication protocol used by the Google Gemini web application and how the standalone client in `test.py` communicates directly with Google's backend.

---

## 1. How the StreamGenerate Protocol Works

The Gemini web application interacts with the Google backend using a specific HTTP RPC endpoint:

### A. The Endpoint
* **URL**: `https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate`
* **Query Parameters**:
  - `bl`: The backend version identifier string (e.g., `boq_assistant-bard-web-server_20260525.09_p0`). If outdated, the server returns an HTTP 400 error.
  - `hl`: The UI language code (`en` for English).
  - `_reqid`: An integer request ID sequence (calculated using epoch time: `int(time.time()) % 1000000`).
  - `rt`: `c` which triggers chunked, streaming responses.

### B. Headers
The request must include specific browser headers to pass CSRF validation and security constraints:
- `Content-Type`: `application/x-www-form-urlencoded`
- `Origin`: `https://gemini.google.com`
- `Referer`: `https://gemini.google.com/app`
- `X-Same-Domain`: `1`
- `User-Agent`: A modern browser user agent (e.g. Chrome/Firefox).

### C. Request Payload (`f.req`)
The payload is passed in the request body under the key `f.req`. It is structured as a twice-serialized JSON array:

1. **Outer Array**: `[null, "inner_json_string"]`
2. **Inner Array**: A JSON list containing 102 items (`[None] * 102`):
   - `[0]`: Contains the user prompt `[prompt, 0, null, null, null, null, 0]`.
   - `[1]`: Language config `["en"]`.
   - `[17]`: Thinking depth `[[0]]` (Deepest) vs `[[4]]` (Shallowest/Off).
   - `[59]`: Session identification UUID string.
   - `[79]`: Model Category ID:
     * `1` = `gemini-3.5-flash` (Default)
     * `2` = `gemini-3.5-flash-thinking`
     * `3` = `gemini-3.1-pro` (Requires cookies)
     * `4` = `gemini-auto`
     * `5` = `gemini-3.5-flash-thinking-lite`
     * `6` = `gemini-flash-lite`

---

## 2. Reverse Engineering Using Chrome DevTools

To verify, modify, or update this implementation as Google changes its parameters:

1. Open Google Chrome and log into [gemini.google.com](https://gemini.google.com/).
2. Open Chrome DevTools (`F12`) and switch to the **Network** tab.
3. Check the **Fetch/XHR** filter and search for `StreamGenerate` in the filter input field.
4. Send a prompt to the chat interface. A network request will appear.
5. Click the request and look at:
   - **General / Request URL**: Inspect query parameters, including the latest `bl` version.
   - **Request Headers**: Review `Cookie` values if you need to authenticate (for Pro models).
   - **Payload**: Copy the value of `f.req` and URL-decode it.
   - **Response**: Inspect the raw stream to see the envelopes containing response text.

---

## 3. Extracting and Parsing the Response

The server sends responses back in chunked text streams.
1. The script filters the response body line-by-line looking for envelopes containing `"wrb.fr"`.
2. Each matching line represents a serialized JSON structure:
   ```text
   [["w", "wrb.fr", "inner_envelope_string"]]
   ```
3. `inner_envelope_string` is parsed as JSON. Index `[4]` contains the generated assistant parts.
4. The script collects text segments recursively and filters out internal metadata, returning the longest accumulated reply.

---

## 4. How `test.py` is Structured

The [test.py](test.py) script implements the full standalone client:

* **`clean_text(text)`**: Removes code execution placeholders and media card links injected by the backend.
* **`extract_texts_from_line(line)`**: Parses the complex stream envelopes.
* **`ask_gemini_direct(prompt, model, think_level)`**: Automatically builds the twice-serialized nested payload, maps the requested model, configures correct headers, sends the POST request to the `StreamGenerate` endpoint, and decodes the stream.

### Running the Test
You can execute the test locally using:
```bash
python -X utf8 test.py
```
