import io
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "http://hw1.alexbers.com/"
USER_ID = "700afb5d21de2bb99d299a77f640b01a"

session = requests.Session()
session.cookies.set("user", USER_ID)


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


def send_request(html, task):
    route = parse_route(html)
    params, headers, body, cookies = parse_parameters(html)
    cookies["user"] = USER_ID
    url = BASE_URL.rstrip("/") + "/" + route.lstrip("/")
    kwargs = {}

    if task == "POST":
        kwargs["data"] = body

    elif task == "UPLOAD":
        files = parse_upload_files(html)
        kwargs["files"] = [
            (
                "file",
                (
                    filename,
                    io.BytesIO(content.encode("utf-8")),
                    "text/plain"
                )
            )
            for filename, content in files.items()
        ]

        print(f"Файлов: {len(files)}")

    method = "GET" if task in ("GET", "LINK") else "POST"
    print(f"[{method}] {url}")
    response = session.request(
        method=method,
        url=url,
        params=params,
        headers=headers,
        cookies=cookies,
        **kwargs
    )
    response.raise_for_status()

    return response.text


def main():
    response = session.get(BASE_URL)
    response.raise_for_status()
    html = response.text
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
