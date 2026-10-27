"""Read cited HTTPS evidence without allowing access to private network hosts."""
from html.parser import HTMLParser
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


def normalized(value):
    return ' '.join(str(value).split()).casefold()


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Địa chỉ nguồn không thuộc mạng công khai')
    return addresses[0][4][0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def verify_source(source):
    """Verify the cited quote exists, without claiming its factual/legal correctness."""
    output = {key: str(source.get(key, ''))[:2000] for key in ('url', 'title', 'quote')}
    output['verified'] = False
    try:
        target = urlsplit(output['url'])
        if (target.scheme != 'https' or not target.hostname or target.port not in (None, 443)
                or target.username or target.password
                or any(ord(char) < 33 for char in output['url'])):
            raise ValueError('Chỉ đọc nguồn HTTPS công khai')
        if len(normalized(output['quote'])) < 30:
            raise ValueError('Trích dẫn cần ít nhất 30 ký tự để đối chiếu')
        connection = PinnedHTTPS(target.hostname, public_address(target.hostname))
        try:
            connection.request('GET', target.path + ('?' + target.query if target.query else '') or '/',
                               headers={'User-Agent': 'MapPredictApp/1.0 evidence-check', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError('Nguồn không trả nội dung trực tiếp, chưa đối chiếu được')
            if not any(kind in response.getheader('Content-Type', '') for kind in ('text/html', 'text/plain')):
                raise ValueError('Nguồn chưa hỗ trợ đối chiếu văn bản')
            content = response.read(512_001)
            if len(content) > 512_000:
                raise ValueError('Nguồn vượt giới hạn đối chiếu')
            parser = Text()
            parser.feed(content.decode('utf-8', errors='replace'))
            if normalized(output['quote']) not in normalized(' '.join(parser.parts)):
                raise ValueError('Không tìm thấy nguyên văn trích dẫn trong nguồn')
            output['verified'] = True
            output['status'] = 'Đã đối chiếu trích dẫn, chưa xác nhận tính đúng của nhận định'
        finally:
            connection.close()
    except Exception:
        output['status'] = 'Chưa đối chiếu được trích dẫn, không dùng để tự điền điểm'
    return output
