from locust import HttpUser, TaskSet, task, between

class BillAccessTaskSet(TaskSet):
    @task
    def view_bills(self):
        self.client.get("/bills")

class WebsiteUser(HttpUser):
    tasks = [BillAccessTaskSet]
    wait_time = between(1, 5)
