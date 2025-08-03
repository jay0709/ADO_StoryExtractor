## Starting and Stopping the API Server

To interact with the API, you first need to start the server. The server can be easily started and stopped using the `monitor_daemon.py` script.

### Starting the Server
1. Open your terminal.
2. Navigate to the directory where the ADO Story Extractor is located.
3. Run the command to start the server:
   ```bash
   python monitor_daemon.py --mode api --host 0.0.0.0 --port 5000
   ```
   - This will start the server on all available network interfaces (`0.0.0.0`) at port `5000`.

### Stopping the Server
- To stop the server, you can simply terminate the process by pressing `Ctrl+C` in the terminal where it's running.

# API Documentation

The ADO Story Extractor provides a REST API for controlling and interacting with the EPIC change monitoring service. Below is a comprehensive description of the available endpoints and their usage.

---

### **GET /api/health**
**Description**: Performs a health check on the API service.

**Response**: 
- **200 OK**: Returns the health status with a timestamp and whether the monitor is running.

Example Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-08-03T15:36:25Z",
  "monitor_running": true
}
```

---

### **GET /api/status**
**Description**: Retrieves the current status of the EPIC monitoring service.

**Response**: 
- **200 OK**: Returns the monitoring status or indicates if the monitor is not initialized.

Example Response:
```json
{
  "is_running": true,
  "monitored_epics": [...]
}
```

---

### **POST /api/start**
**Description**: Starts the EPIC monitoring service.

**Response**:
- **200 OK**: Indicates that the monitor started successfully.
- **400 BAD REQUEST**: Monitor is already running.
- **500 INTERNAL SERVER ERROR**: An error occurred starting the monitor.

Example Response:
```json
{
  "success": true,
  "message": "Monitor started successfully"
}
```

---

### **POST /api/stop**
**Description**: Stops the EPIC monitoring service.

**Response**:
- **200 OK**: Monitor stopped successfully.
- **400 BAD REQUEST**: Monitor is not running.
- **500 INTERNAL SERVER ERROR**: An error occurred stopping the monitor.

Example Response:
```json
{
  "success": true,
  "message": "Monitor stopped successfully"
}
```

---

### **GET /api/epics**
**Description**: Lists all EPICs currently being monitored.

**Response**:
- **200 OK**: Returns a list of monitored EPICs.

Example Response:
```json
{
  "epics": [...],
  "details": {...}
}
```

---

### **POST /api/epics/<epic_id>**
**Description**: Adds an EPIC to the monitoring service.

**Path Parameters**:
- `<epic_id>`: The ID of the EPIC to add.

**Response**:
- **200 OK**: EPIC added to monitoring successfully.
- **400 BAD REQUEST**: Failed to add EPIC.
- **500 INTERNAL SERVER ERROR**: An error occurred.

---

### **DELETE /api/epics/<epic_id>**
**Description**: Removes an EPIC from the monitoring service.

**Path Parameters**:
- `<epic_id>`: The ID of the EPIC to remove.

**Response**:
- **200 OK**: EPIC removed successfully.
- **400 BAD REQUEST**: EPIC was not being monitored or monitor not initialized.
- **500 INTERNAL SERVER ERROR**: An error occurred.

---

### **POST /api/check**
**Description**: Forces a check on monitored EPICs to detect changes.

**Request Body** (Optional):
- `epic_id`: Specify an EPIC ID to check a specific EPIC.

**Response**:
- **200 OK**: Returns results of the force check.
- **400 BAD REQUEST**: Monitor not initialized.
- **500 INTERNAL SERVER ERROR**: An error occurred during the check.

---

### **GET /api/config**
**Description**: Retrieves the current configuration of the monitoring service.

**Response**:
- **200 OK**: Returns the current config.

---

### **PUT /api/config**
**Description**: Updates the monitoring configuration (requires a restart to take effect).

**Request Body**:
```json
{
  "poll_interval_seconds": 300,
  "auto_sync": true,
  "epic_ids": [...]
}
```

**Response**:
- **200 OK**: Configuration updated.
- **500 INTERNAL SERVER ERROR**: An error occurred updating the configuration.

---

### **GET /api/logs**
**Description**: Retrieves recent entries from the application logs.

**Query Parameters**:
- `lines`: (Optional) Number of lines to retrieve. Default is 100.

**Response**:
- **200 OK**: Returns the requested log entries.
- **500 INTERNAL SERVER ERROR**: An error occurred accessing the logs.

---

Please replace `<epic_id>` in the URL with the actual EPIC ID you wish to interact with. Responses to all endpoints are in JSON format.
