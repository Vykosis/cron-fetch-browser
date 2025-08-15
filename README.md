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

A standalone Python script that checks a Neon database for scheduled tasks and executes them using browser automation.

## Overview

This script replaces the previous FastAPI application with a standalone task runner that:

1. Connects to your Neon database
2. Queries for active scheduled tasks that are due for execution
3. Executes each task using browser automation via Browserbase
4. Updates the `last_run_at` timestamp for each completed task

## Features

- **Database Integration**: Connects to Neon PostgreSQL database
- **Smart Scheduling**: Parses schedule strings like "every 1 hour", "every 30 minutes", etc.
- **Browser Automation**: Uses Browserbase for reliable browser automation
- **Error Handling**: Robust error handling with proper cleanup
- **Logging**: Detailed console output for monitoring

## Environment Variables

Set these environment variables in your Railway project:

- `DATABASE_URL`: Your Neon database connection string
- `BROWSERBASE_API_KEY`: Your Browserbase API key
- `BROWSERBASE_PROJECT_ID`: Your Browserbase project ID

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

## Deployment on Railway

1. **Connect your repository** to Railway
2. **Set environment variables** in the Railway dashboard:
   - `DATABASE_URL`
   - `BROWSERBASE_API_KEY`
   - `BROWSERBASE_PROJECT_ID`
3. **Deploy** - Railway will automatically build and deploy your script

## How It Works

1. The script runs once when started
2. It queries the database for all active tasks (`is_active = true`)
3. For each task, it checks if it's due for execution based on:
   - `last_run_at` timestamp
   - `schedule` string
4. If a task is due, it:
   - Creates a Browserbase session
   - Executes the task using browser automation
   - Updates the `last_run_at` timestamp
   - Cleans up browser resources

## Monitoring

The script provides detailed console output including:
- Task execution status
- Browser session management
- Error messages and stack traces
- Timing information

## Error Handling

- If a task fails, the `last_run_at` is still updated to prevent infinite retries
- Browser sessions are properly cleaned up even on errors
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
   BROWSERBASE_API_KEY=your_browserbase_api_key
   BROWSERBASE_PROJECT_ID=your_browserbase_project_id
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

2. **Browserbase API Errors**
   - Verify your `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID`
   - Check your Browserbase account status

3. **Task Not Running**
   - Verify the task is marked as `is_active = true`
   - Check the `schedule` format is supported
   - Ensure `last_run_at` is properly set

### Logs

Check Railway logs for detailed error messages and execution status.
