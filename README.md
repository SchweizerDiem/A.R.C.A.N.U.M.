# A.R.C.A.N.U.M.
**Automated Routing & Controlling Agents Network for Urban Mobility**

## Overview
This project focuses on the design and implementation of an **Automated Routing & Controlling Agents Network for Urban Mobility** to efficiently manage traffic at intersections, aiming to minimize waiting times and enhance overall traffic flow. The system utilizes a multi-agent approach, where different components of the traffic environment (lights, vehicles, coordination) are represented by autonomous agents that communicate and coordinate to achieve optimal performance.

The project is developed for the **Artificial Intelligence** course, part of the **Informatics Engineering Degree** program at ISPGaya.


---

## Technologies
This project leverages the following key technologies:

* **Python**: The primary programming language for implementing the agents and simulation logic.
* **Spade**: A Python framework for developing **Multi-Agent Systems (MAS)** based on the FIPA standards. It facilitates agent communication and behavior management.
* **SUMO (Simulation of Urban MObility)** (Assumed integration, common for traffic simulation): Used to simulate the traffic environment and provide a realistic setting for the agents to perceive and act upon.
* **Machine Learning (ML)**: Utilized within the Disruption Management Agent for predicting traffic disruptions.

---

## Project Features

The A.R.C.A.N.U.M. is designed to incorporate several intelligent features:

### 1. Multi-Agent Components
* **Traffic Environment**: A simulated environment (via SUMO) that agents can perceive and act on.
* **Traffic Light Agent(s)**: Control traffic light timings (Red, Green, Yellow) dynamically based on real-time traffic conditions.
* **Vehicle Agents**: Simulate realistic vehicle traffic patterns, react to traffic lights, and report metrics like waiting times. They may also be able to request light changes.
* **Central Coordination Agent**: Gathers data from other agents to manage broader traffic patterns and intervene in special circumstances.
* **Disruption Management Agent**: Predicts traffic disruptions (e.g., bad weather, construction) using a **Machine Learning model** and issues warnings for adaptive behavior by other agents.

### 2. Core Functionalities
* **Real-Time Adjustments**: Traffic light agents dynamically change light timings based on traffic volume to improve flow.
* **Emergency Vehicle Priority**: Emergency vehicles (ambulance, fire brigade, police) are given the highest priority, allowing them to interact with Traffic Light Agents to secure a green light.
* **Performance Metrics**: Implementation of metrics to measure system efficiency, such as waiting time and vehicle throughput.

---

## Setup and Development Guide (Python + Spade)

To get started with the project, follow the environment setup steps below. We are using **Python** and the **Spade** framework for the agent implementation.

### Prerequisites

* Python (Installation guide should be followed) 
* Spade (Tutorial should be completed)
* SUMO (Installation and basic environment setup)

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SchweizerDiem/A.R.C.A.N.U.M.
    cd A.R.C.A.N.U.M.
    ```

2.  **Set up Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Complete Spade Tutorial:**
    Make sure to follow the Spade tutorial as outlined in the course materials to familiarize yourself with agent creation and communication.

---

## Project Milestones

The project is structured with the following key milestones over 12 weeks:

| Weeks | Focus Area | Key Deliverables |
| :---: | :--- | :--- |
| **1-2** | Project Kickoff and Planning | Project teams formed, roles assigned, project timeline outlined, code environment set up. |
| **3-4** | Environment Setup and Basic Agents | Traffic environment simulation setup. Basic framework for agents. Implementation of basic Traffic Light and Vehicle Agents with communication channels. |
| **5-6** | Traffic Light Agent Improvement | Enhanced Traffic Light Agent logic for real-time adaptation and real-time adjustments based on traffic volume. Start tracking performance metrics. |
| **7-8** | Vehicle Agent Behavior and Interaction | Improved Vehicle Agent behavior (response to lights, waiting time reporting). Implementation of the **Emergency Vehicle Priority** feature. |
| **9-10**| Disruption Management and Prediction | Development of the **Disruption Management Agent**. Implementation and integration of a **Machine Learning model** for disruption prediction. |
| **11-12**| Central Coordination and Final Testing | Creation of the **Central Coordination Agent** with coordination logic. Comprehensive system testing, data collection, and final report preparation. |
