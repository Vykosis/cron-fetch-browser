---
title: FastAPI
description: A FastAPI server
tags:
  - fastapi
  - hypercorn
  - python
---

# FastAPI Example

This example starts up a [FastAPI](https://fastapi.tiangolo.com/) server.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/-NvLj4?referralCode=CRJ8FE)
## ✨ Features

- FastAPI
- [Hypercorn](https://hypercorn.readthedocs.io/)
- Python 3

## 💁‍♀️ How to use

- Clone locally and install packages with pip using `pip install -r requirements.txt`
- Run locally using `hypercorn main:app --reload`

## 📝 Notes

- To learn about how to use FastAPI with most of its features, you can visit the [FastAPI Documentation](https://fastapi.tiangolo.com/tutorial/)
- To learn about Hypercorn and how to configure it, read their [Documentation](https://hypercorn.readthedocs.io/)

# Cron Fetch Browser Task Runner

A standalone Python script that checks a Neon database for scheduled tasks and executes them using Browser-Use Cloud API.

## Overview

This script replaces the previous FastAPI application with a standalone task runner that:

1. Connects to your Neon database
2. Queries for active scheduled tasks that are due for execution
3. Executes each task using Browser-Use Cloud API
4. Updates the `last_run_at` timestamp for each completed task

## Features

- **Database Integration**: Connects to Neon PostgreSQL database
- **Smart Scheduling**: Parses schedule strings like "every 1 hour", "every 30 minutes", etc.
- **Browser Automation**: Uses Browser-Use Cloud API for reliable browser automation
- **Error Handling**: Robust error handling with proper cleanup
- **Logging**: Detailed console output for monitoring
- **Async HTTP**: Uses aiohttp for efficient API communication

## Environment Variables

Set these environment variables in your Railway project:

- `DATABASE_URL`: Your Neon database connection string
- `BROWSER_USE_API_KEY`: Your Browser-Use Cloud API key

## Database Schema

The script expects a `scheduled_tasks` table with the following structure:

```sql
CREATE TABLE scheduled_tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    query TEXT NOT NULL,
    data_structure TEXT,
    schedule TEXT NOT NULL,
    last_run_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Schedule Format

The script supports the following schedule formats:

- `"every 1 hour"` - Run every hour
- `"every 30 minutes"` - Run every 30 minutes
- `"every 2 days"` - Run every 2 days
- `"every 1 day"` - Run daily

If the schedule format is unclear, it defaults to running every hour.

## Browser-Use Cloud API Integration

The script uses the Browser-Use Cloud API to execute browser automation tasks:

- **Task Execution**: Sends tasks to the Browser-Use Cloud API
- **Status Polling**: Monitors task status until completion
- **Structured Output**: Supports structured JSON output if specified
- **Error Handling**: Handles API errors and timeouts gracefully

## Deployment on Railway

1. **Connect your repository** to Railway
2. **Set environment variables** in the Railway dashboard:
   - `DATABASE_URL`
   - `BROWSER_USE_API_KEY`
3. **Deploy** - Railway will automatically build and deploy your script

## How It Works

1. The script runs once when started
2. It queries the database for all active tasks (`is_active = true`)
3. For each task, it checks if it's due for execution based on:
   - `last_run_at` timestamp
   - `schedule` string
4. If a task is due, it:
   - Sends the task to Browser-Use Cloud API
   - Polls for task completion
   - Updates the `last_run_at` timestamp
   - Logs the results

## Monitoring

The script provides detailed console output including:
- Task execution status
- API request/response details
- Task polling progress
- Error messages and stack traces
- Timing information

## Error Handling

- If a task fails, the `last_run_at` is still updated to prevent infinite retries
- API errors are caught and logged
- Network timeouts are handled gracefully
- Database connections are properly closed
- Missing environment variables are detected and reported

## Local Development

To run locally:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in a `.env` file:
   ```
   DATABASE_URL=your_neon_connection_string
   BROWSER_USE_API_KEY=your_browser_use_api_key
   ```

3. Run the script:
   ```bash
   python main.py
   ```

## Railway Cron Setup

To run this script periodically on Railway, you can:

1. **Use Railway's built-in cron** (if available)
2. **Set up a GitHub Action** that triggers Railway deployments
3. **Use an external cron service** like cron-job.org to hit a Railway webhook

For continuous operation, consider setting up a GitHub Action that:
- Runs every X minutes/hours
- Triggers a Railway deployment
- The script runs once and exits
- Railway restarts the service for the next scheduled run

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check your `DATABASE_URL` environment variable
   - Ensure your Neon database is accessible

2. **Browser-Use API Errors**
   - Verify your `BROWSER_USE_API_KEY` environment variable
   - Check your Browser-Use account status and API limits
   - Ensure the API key has proper permissions

3. **Task Not Running**
   - Verify the task is marked as `is_active = true`
   - Check the `schedule` format is supported
   - Ensure `last_run_at` is properly set

4. **Task Timeout**
   - Tasks have a 5-minute timeout by default
   - Check if the task is taking too long to complete
   - Verify the task query is valid

### Logs

Check Railway logs for detailed error messages and execution status.

## API Response Format

The script expects Browser-Use Cloud API responses in the following format:

```json
{
  "id": "task_id_here",
  "status": "completed|running|failed|pending",
  "result": "task_result_here",
  "error": "error_message_if_failed"
}
```
