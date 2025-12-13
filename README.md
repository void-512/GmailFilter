# Gmail Order Fetching & Processing System

## Overview

This project is an **email ingestion and filtering system**, one of the core service in the workflow of Garde Robe

The system automatically fetches emails from users, applies configurable keyword and pattern-based filters, extracts structured information, and forwards matched results to downstream services


## Usage

### Config

The project includes 3 config files: **auth.json**, **config.json**, and **keywords.json**
#### auth.json
```json
{
    "auth_endpoint": {
        "user": "usr1",
        "pwd": "abcd"
    },
    "fetcher_endpoint": {
        "user": "usr2",
        "pwd": "1234"
    }
}
```
- **auth_endpoint**: The basic authentication to ask for user tokens from upstream service (this is determined by upstream service)
- **fetcher_endpoint**: The basic authentication to receive tokens from upstream service (this is determined by yourself)

#### config.json
```json
{
  "numMsgPerBatch": 5000,
  "keywordFile": "keywords.json",
  "scopes": "https://www.googleapis.com/auth/gmail.readonly",
  "dbPath": "users.db",
  "defaultStartDate": "2023/01/01",
  "maxThreads": 8
}
```
- **numMsgPerBatch**: Number of messages fetched and processed per batch (higher value may slightly increase performance, with a higher RAM usage)
- **keywordFile**: Path to the keyword and pattern configuration file used by the filtering engine
- **scopes**: Gmail API OAuth scope used for email access
- **dbPath**: SQLite database file storing user metadata and processing state
- **defaultStartDate**: Initial email fetch start date for newly onboarded users
- **maxThreads**: Maximum number of worker threads used for concurrent processing

 #### keywords.json
```json
{
  "include_all_keywords": {
    "filter1": ["thank you for your purchase"],
    "filter2": ["order"]
    },
  "exclude_any_keywords": ["shipment-tracking@amazon.com"],
  "order_id_patterns": ["ORDER NUMBER\\s\\d{11}"],
  "domains": ["hm.com"],
  "return_keywords": ["refund"]
}
```
- **include_all_keywords**: Requires that an email contain at least one keyword from *each* defined group to be considered a valid match
- **exclude_any_keywords**: Immediately rejects any email containing one or more of the specified keywords
- **order_id_patterns**: Defines regular expressions used to detect valid order id
- **domains**: Restricts processing to emails sent from approved sender domains only
- **return_keywords**: Identifies refund or return–related emails and is reserved for future classification or workflow expansion (currently useless)

## API Documentation

### Endpoint

- **URL**: `/`
- **Method**: `POST`
- **Authentication**: HTTP Basic Authentication
- **Content-Type**: `application/json`

#### Authentication

The endpoint is protected using **HTTP Basic Auth**.

- Username and password are validated server-side against values stored in `auth.json`
- Requests without valid credentials will receive `401 Unauthorized`


#### Request Body

```json
{
  "bubble_user_id": "string"
}
```

### Token Acquisition

#### Overview

The system retrieves Gmail OAuth access tokens for each user via internal authentication service
Expire dates will be stored internally, refresh request will be made only when expire date passes


#### Token Source

- **Endpoint**: [Internal authentication service ](https://auth.garde-robe.com/auth/token) 
- **Method**: `GET`
- **Authentication**: HTTP Basic Authentication, authenticated with *auth_endpoint* in *auth.json*
- **Purpose**: Exchange a `bubble_user_id` for a Gmail OAuth access token


#### Request Parameters

```http
GET /auth/token?bubble_user_id=<USER_ID>
```