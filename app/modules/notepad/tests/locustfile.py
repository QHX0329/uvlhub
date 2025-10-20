from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token
import re


class NotepadBehavior(TaskSet):
    def on_start(self):
        # keep a small local cache of created notepad ids to exercise view/edit/delete
        self.notepad_ids = []
        self.index()

    def _extract_id_from_location_or_html(self, response):
        # Try Location header first
        loc = response.headers.get("Location") if hasattr(response, "headers") else None
        if loc:
            m = re.search(r"/notepad/(\d+)", loc)
            if m:
                return int(m.group(1))

        # Try to find /notepad/<id> in response text
        m = re.search(r"/notepad/(\d+)", response.text)
        if m:
            return int(m.group(1))

        return None

    @task(5)
    def index(self):
        response = self.client.get("/notepad")

        if response.status_code != 200:
            print(f"Notepad index failed: {response.status_code}")

    @task(4)
    def create(self):
        # GET the create page to obtain CSRF token
        resp = self.client.get("/notepad/create")
        try:
            csrf_token = get_csrf_token(resp)
        except Exception as exc:
            print(f"Failed to get CSRF token for notepad create: {exc}")
            return

        title = fake.sentence(nb_words=4)
        body = fake.paragraph(nb_sentences=3)

        post = self.client.post(
            "/notepad/create",
            data={"title": title, "body": body, "csrf_token": csrf_token},
        )

        if post.status_code not in (200, 302):
            print(f"Notepad create failed: {post.status_code}")
            return

        # Try to extract created id from redirect or response content (best effort)
        # If the response contains the title we posted, we assume it was created successfully.
        if title in post.text:
            # Try to extract id
            created_id = self._extract_id_from_location_or_html(post)
            if created_id:
                self.notepad_ids.append(created_id)
            else:
                # fallback to using the title marker so we can try to discover id later
                self.notepad_ids.append(title)

    @task(3)
    def view(self):
        if not self.notepad_ids:
            return
        nid = self.notepad_ids[-1]
        # If nid is a title (str), try to discover its id by scanning the index
        if isinstance(nid, str):
            r = self.client.get('/notepad')
            m = re.search(r"/notepad/(\d+).*>\s*%s" % re.escape(nid), r.text)
            if m:
                nid = int(m.group(1))
                self.notepad_ids[-1] = nid
            else:
                return

        resp = self.client.get(f"/notepad/{nid}")
        if resp.status_code != 200:
            print(f"Notepad view failed for id {nid}: {resp.status_code}")

    @task(2)
    def edit(self):
        if not self.notepad_ids:
            return
        nid = self.notepad_ids[-1]
        if isinstance(nid, str):
            # try to resolve title to id via index
            r = self.client.get('/notepad')
            m = re.search(r"/notepad/(\d+).*>\s*%s" % re.escape(nid), r.text)
            if m:
                nid = int(m.group(1))
                self.notepad_ids[-1] = nid
            else:
                return

        # GET edit form to grab csrf
        resp = self.client.get(f"/notepad/edit/{nid}")
        try:
            csrf = get_csrf_token(resp)
        except Exception:
            # If no csrf, still try a POST
            csrf = None

        new_title = fake.sentence(nb_words=3)
        new_body = fake.paragraph(nb_sentences=2)

        data = {"title": new_title, "body": new_body}
        if csrf:
            data["csrf_token"] = csrf

        post = self.client.post(f"/notepad/edit/{nid}", data=data)
        if post.status_code not in (200, 302):
            print(f"Notepad edit failed for id {nid}: {post.status_code}")

    @task(1)
    def delete(self):
        if not self.notepad_ids:
            return
        nid = self.notepad_ids.pop(0)
        if isinstance(nid, str):
            # attempt to resolve
            r = self.client.get('/notepad')
            m = re.search(r"/notepad/(\d+).*>\s*%s" % re.escape(nid), r.text)
            if m:
                nid = int(m.group(1))
            else:
                return

        # Try to get CSRF from index/show page
        r = self.client.get(f"/notepad/{nid}")
        try:
            csrf = get_csrf_token(r)
        except Exception:
            csrf = None

        data = {}
        if csrf:
            data["csrf_token"] = csrf

        resp = self.client.post(f"/notepad/delete/{nid}", data=data)
        if resp.status_code not in (200, 302):
            print(f"Notepad delete failed for id {nid}: {resp.status_code}")


class NotepadUser(HttpUser):
    tasks = [NotepadBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
