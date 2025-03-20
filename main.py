from fastapi import FastAPI, UploadFile, File
import json
import networkx as nx
import asyncio
import random
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from collections import deque
from prettytable import PrettyTable

app = FastAPI()

# Simulated health check function
def check_component_health():
    return random.choice(["Healthy", "Unhealthy"])

# Function to process the JSON and create a DAG
def create_graph(data):
    G = nx.DiGraph()
    for node, dependencies in data.items():
        G.add_node(node)
        for dep in dependencies:
            G.add_edge(dep, node)
    return G

# Asynchronous health check using BFS traversal
async def check_health(G):
    health_status = {}
    tasks = []
    queue = deque([node for node in G if G.in_degree(node) == 0])  # Start BFS from root nodes

    async def check(node):
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulated async call delay
        health_status[node] = check_component_health()

    while queue:
        node = queue.popleft()
        tasks.append(asyncio.create_task(check(node)))
        
        for neighbor in G.successors(node):
            queue.append(neighbor)

    await asyncio.gather(*tasks)
    return health_status

# Function to generate a health status table
def generate_health_table(health_status):
    table = PrettyTable(["Component", "Health Status"])
    for component, status in health_status.items():
        table.add_row([component, status])
    return table.get_string()

# Function to generate and save the graph image
def generate_graph_image(G, health_status, filename="dag_health.png"):
    plt.figure(figsize=(8, 5))
    pos = nx.spring_layout(G)
    
    # Color nodes based on health status
    colors = ["red" if health_status[node] == "Unhealthy" else "green" for node in G.nodes()]
    
    nx.draw(G, pos, with_labels=True, node_color=colors, edge_color='black', node_size=2000, font_size=10)
    
    # Save the image locally
    plt.savefig(filename)
    plt.close()
    
    # Convert image to base64 for API response
    with open(filename, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    
    return img_base64

# API endpoint to upload the JSON file
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    data = json.loads(await file.read())
    G = create_graph(data)
    health_status = await check_health(G)
    
    # Generate health status table
    health_table = generate_health_table(health_status)
    
    # Generate and save graph image
    img_base64 = generate_graph_image(G, health_status)

    return {
        "health_status": health_status,
        "health_table": health_table,
        "graph_image": f"data:image/png;base64,{img_base64}"
    }
