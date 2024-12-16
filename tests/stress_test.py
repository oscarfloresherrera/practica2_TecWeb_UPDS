from locust import HttpUser, TaskSet, task, between

class StressTaskSet(TaskSet):
    @task
    def view_products(self):
        self.client.get("/products")

    @task
    def view_clients(self):
        self.client.get("/clients")

class WebsiteUser(HttpUser):
    tasks = [StressTaskSet]
    wait_time = between(0.5, 1)  # Simula tiempos de espera cortos
    
    
