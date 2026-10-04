# API Overview

Base path: `/api/v1`

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/register | Register a user |
| POST | /auth/login | Obtain JWT |
| GET | /auth/me | Current user |

## Question Bank

| Method | Path | Description |
|--------|------|-------------|
| POST | /subjects | Create subject |
| GET | /subjects | List subjects |
| POST | /topics | Create topic |
| GET | /topics | List topics |
| POST | /questions | Create question |
| GET | /questions | List questions |
| GET | /questions/{id} | Get question |
| PATCH | /questions/{id} | Update question |

## Examinations

| Method | Path | Description |
|--------|------|-------------|
| POST | /exams | Create exam |
| GET | /exams | List exams |
| GET | /exams/{id} | Get exam |
| PATCH | /exams/{id} | Update exam |
| POST | /exams/{id}/publish | Publish exam |

## Attempts & Results

| Method | Path | Description |
|--------|------|-------------|
| POST | /exams/{id}/start | Start attempt |
| GET | /attempts/{id} | Get attempt + questions |
| POST | /attempts/{id}/answers | Submit answer |
| DELETE | /attempts/{id}/answers/{qid} | Clear answer |
| POST | /attempts/{id}/submit | Submit attempt |
| GET | /results/{id} | Get result |
| GET | /exams/{id}/results | List results (examiner) |

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Service health |
| GET | /health/database | Database connectivity |

Interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.
