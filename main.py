import re
import base64
import scrapy
import json
import time
from twisted.internet import reactor, defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from scrapy import Request

proxies_json_path = "proxies.json"


class ProxiesSpider(scrapy.Spider):
    name = "proxies"
    parse_pages = 5
    custom_settings = {
        'DOWNLOAD_DELAY': 2
    }

    def __init__(self):
        super().__init__()
        self.result = []

    def start_requests(self):
        for page in range(1, 1 + self.parse_pages):
            yield scrapy.Request(url=f"http://free-proxy.cz/en/proxylist/main/{page}",
                                 callback=self.parse)

    def parse(self, response, **kwargs):

        # Regex pattern to extract IP address
        pattern = re.compile(r"decode\(\"([a-zA-Z\d\W]*)\"\)")

        for proxy in response.xpath("//table[@id='proxy_list']/tbody/tr"):

            # Get port
            port = proxy.xpath(".//*[@class='fport']/text()").get()

            # Check if port is not null
            if not port:
                continue

            # Extracting IP address and decoding from base64
            ip_address_text = proxy.xpath(".//td[1]/script/text()").get()
            ip_address_b64 = re.findall(pattern, ip_address_text)[0]
            ip_address_encoded = base64.b64decode(ip_address_b64)
            ip_address = ip_address_encoded.decode('utf-8')

            # Store data
            self.result.append({"ip_address": ip_address, "port": port})

    def close(self, reason):
        with open(proxies_json_path, 'w') as file:
            file.write(json.dumps(self.result))


class FormSpider(scrapy.Spider):
    name = "form"
    start_urls = [
        "https://test-rg8.ddns.net/api/get_token"
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 13
    }

    def __init__(self, *args, **kwargs):
        # Execute Super-class method
        super().__init__()

        # Define POST request URL and user id
        self.post_method_url = "https://test-rg8.ddns.net/api/post_proxies"
        self.user_id = "t_536124ef"
        self.result_dict = {}

        # Get the proxies list from JSON file
        with open(proxies_json_path, 'r') as file:
            prx_list = file.read()
        self.proxies_list = json.loads(prx_list)

    def parse(self, response, **kwargs):
        """
        Parses the form token and calls POST request
        """
        # Form token parsing
        set_cookie = response.headers.get("Set-Cookie").decode("utf-8")
        re_pattern = re.compile(r"form_token=([^;]+)")
        form_token = re.search(re_pattern, set_cookie).group(1)

        # Call POST request function
        return self.get_save_id_request(form_token)

    def get_save_id_request(self, form_token):
        # Processing proxies for payload and save
        proxies_str = ""
        proxies_to_save = []

        if len(self.proxies_list) >= 10:
            length = 10
        else:
            length = len(self.proxies_list)

        for index, proxy in enumerate(self.proxies_list):
            if index == 10:
                break
            else:
                proxies_to_save.append(f'{proxy["ip_address"]}:{proxy["port"]}')
                proxies_str += f'{proxy["ip_address"]}:{proxy["port"]}, '
        proxies_str = proxies_str.strip(", ")

        self.proxies_list = self.proxies_list[length:]

        # Request data
        payload = {
            "user_id": self.user_id,
            "len": length,
            "proxies": proxies_str
        }
        cookies = {
            "x-user_id": self.user_id,
            "form_token": form_token
        }
        yield Request(self.post_method_url, callback=self.parse_save_id, cb_kwargs={'proxies': proxies_to_save},
                      method="POST", body=json.dumps(payload), cookies=cookies, dont_filter=True)

    def parse_save_id(self, response, proxies):
        # Get save_id from response
        data = json.loads(response.body)
        save_id = data["save_id"]

        # Store save_id and proxies to the result dictionary
        self.result_dict[f"{save_id}"] = proxies

        # Request if proxies left
        if len(self.proxies_list) > 0:
            return Request(url=self.start_urls[0], method="GET", callback=self.parse, dont_filter=True)

    def close(self, reason):
        """
        Saves result dictionary to file.
        """
        with open('results.json', 'w') as json_file:
            json.dump(self.result_dict, json_file)


settings = get_project_settings()
configure_logging(settings)
runner = CrawlerRunner(settings)


@defer.inlineCallbacks
def crawl():
    # yield runner.crawl(ProxiesSpider)
    yield runner.crawl(FormSpider)
    reactor.stop()


def convert_seconds_to_hh_mm_ss(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


if __name__ == "__main__":
    # Get start execution time
    start_time = time.time()
    print(start_time)

    # Crawl
    crawl()
    reactor.run()

    # Get elapsed time
    elapsed_time = time.time() - start_time
    print(elapsed_time)
    elapsed_time = int(elapsed_time)

    # Save execution time to txt file in hh:mm:ss format
    formatted_time = convert_seconds_to_hh_mm_ss(elapsed_time)
    with open("time.txt", 'w') as f:
        f.write(formatted_time)
