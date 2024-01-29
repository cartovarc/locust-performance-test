from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(5, 15)
    host = "https://x.com"
    
    @task(1)
    def index_page(self):
        self.client.get("/")
