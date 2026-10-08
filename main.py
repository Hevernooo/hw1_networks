import re
import socket
from urllib.parse import urlencode

from bs4 import BeautifulSoup


HOST = "hw1.alexbers.com"
PORT = 80
BASE_URL = f"http://{HOST}/"

USER_ID = "700afb5d21de2bb99d299a77f640b01a"


def parse_route(html):
    soup = BeautifulSoup(html, "html.parser")

    for code in soup.find_all("code"):
        text = code.get_text(strip=True)

        if text.startswith("/"):
            return text

    for link in soup.find_all("a"):
        href = link.get("href")

        if href:
            return href

    match = re.search(r"/[A-Za-z0-9_-]+", soup.get_text())

    if match:
        return match.group(0)

    raise RuntimeError("Не удалось найти адрес запроса")


def parse_parameters(html):
    soup = BeautifulSoup(html, "html.parser")

    params = {}
    headers = {}
    body = {}
    cookies = {}

    markers = {
        "При переходе выставьте следующие параметры запроса, указанные в таблице:": params,
        "Запрос должен иметь следующие заголовки:": headers,
        "Запрос должен иметь следующие данные формы:": body,
        "В запросе должны быть выставлены cookie:": cookies,
    }

    for marker, result in markers.items():
        element = soup.find(string=lambda text: text and marker in text)

        if not element:
            continue

        table = element.find_next("table")

        if not table:
            continue

        for row in table.find_all("tr"):
            cells = row.find_all("td")

            if len(cells) != 2:
                continue

            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)

            result[key] = value

    return params, headers, body, cookies


def parse_upload_files(html):
    soup = BeautifulSoup(html, "html.parser")
    files = {}

    for row in soup.find_all("tr"):
        cells = row.find_all("td")

        if len(cells) != 2:
            continue

        filename = cells[0].get_text(strip=True)
        content = cells[1].get_text()

        files[filename] = content

    return files


def detect_task(html):
    if "Отправьте GET-запрос" in html:
        return "GET"

    if "Отправьте POST-запрос" in html:
        return "POST"

    if "Загрузите файлы по адресу" in html:
        return "UPLOAD"

    if "Перейдите по" in html:
        return "LINK"

    return None


def send_http(method, route, params=None, headers=None,
              cookies=None, body=None, files=None):

    params = params or {}
    headers = headers or {}
    cookies = cookies or {}

    if params:
        route += "?" + urlencode(params)

    if cookies:
        headers["Cookie"] = "; ".join(
            f"{key}={value}"
            for key, value in cookies.items()
        )

    if files is not None:
        boundary = "----Boundary"

        body_bytes = b""

        for filename, content in files.items():
            body_bytes += (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: text/plain\r\n"
                f"\r\n"
            ).encode("utf-8")

            body_bytes += content.encode("utf-8")
            body_bytes += b"\r\n"

        body_bytes += f"--{boundary}--\r\n".encode("utf-8")

        headers["Content-Type"] = (
            f"multipart/form-data; boundary={boundary}"
        )

    elif body is not None:
        body_bytes = urlencode(body).encode("utf-8")

        headers["Content-Type"] = (
            "application/x-www-form-urlencoded"
        )

    else:
        body_bytes = b""

    request = f"{method} {route} HTTP/1.1\r\n"
    request += f"Host: {HOST}\r\n"

    for key, value in headers.items():
        request += f"{key}: {value}\r\n"

    if body_bytes:
        request += f"Content-Length: {len(body_bytes)}\r\n"

    request += "Connection: close\r\n"
    request += "\r\n"

    request = request.encode("utf-8") + body_bytes

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        sock.sendall(request)

        response = b""

        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)

        response_headers, response_body = response.split(
            b"\r\n\r\n",
            1
        )

        content_length = None

        for line in response_headers.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                content_length = int(
                    line.split(b":", 1)[1].strip()
                )
                break

        if content_length is not None:
            while len(response_body) < content_length:
                response_body += sock.recv(4096)

            response_body = response_body[:content_length]

        else:
            while True:
                data = sock.recv(4096)

                if not data:
                    break

                response_body += data

    return response_body.decode(
        "utf-8",
        errors="replace"
    )


def send_request(html, task):
    route = parse_route(html)

    params, headers, body, cookies = parse_parameters(html)

    cookies["user"] = USER_ID

    files = None

    if task == "UPLOAD":
        files = parse_upload_files(html)

        print(f"Файлов: {len(files)}")

    method = "GET" if task in ("GET", "LINK") else "POST"

    print(f"[{method}] {route}")

    return send_http(
        method=method,
        route=route,
        params=params,
        headers=headers,
        cookies=cookies,
        body=body if task == "POST" else None,
        files=files
    )


def main():
    html = send_http(
        method="GET",
        route="/",
        cookies={"user": USER_ID}
    )

    step = 1

    while True:
        print(f"\n--- Шаг {step} ---")

        task = detect_task(html)

        if task is None:
            print("Тип задания не определён.")
            print(html)
            break

        print(f"Задание: {task}")

        html = send_request(html, task)

        if detect_task(html) is None:
            print("\nПолучен финальный ответ:")
            print(html)
            break

        step += 1


if __name__ == "__main__":
    main()
