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
    }
}
```
- **auth_endpoint**: The basic authentication to ask for user tokens from upstream service (this is determined by upstream service)

#### config.json
```json
{
    "numMsgPerBatch": 5000,
    "filterType": "ml",
    "keywordFile": "keywords.json",
    "scopes": "https://www.googleapis.com/auth/gmail.readonly",
    "dbPath": "users.db",
    "defaultStartMonthsAgo": 24,
    "maxThreads": 8,
    "authServiceEndpoint": "https://auth.garde-robe.com/auth/token",
    "downstreamEndpoint": "https://clients-shared-101.helixautomation.dev/webhook/garde-robe/process_email",
    "dailyIncrementalUpdateHour": 2,
    "dailyIncrementalUpdateMinute": 30,
    "mlFilter": {
        "modelName": "model.joblib",
        "threshold": 0.9
    },
    "debug": {
        "startDate": "2023/07/01",
        "endDate": "2023/12/31"
    }
}
```
- **numMsgPerBatch**: Maximum number of messages in the buffer of producer-consumer model (higher value may slightly increase performance, with a higher RAM usage)
- **filterType**: Traditional regular expression matching ```regex``` or experimental machine learning matching ```ml```
- **keywordFile**: Path to the keyword and pattern configuration file used by the filtering engine
- **scopes**: Gmail API OAuth scope used for email access
- **dbPath**: SQLite database file storing user metadata and processing state
- **defaultStartMonthsAgo**: Fetching the email *n* months before today
- **maxThreads**: Maximum number of worker threads used for concurrent processing
- **authServiceEndpoint**: Auth service to get user tokens
- **downstreamEndpoint**: Endpoint of downstream parsing service
- **dailyIncrementalUpdateHour** & **dailyIncrementalUpdateMinute**: Time for incremental update
- **mlFilter**: Config for machine learning filter specifically, effective when ```filterType == 'ml'```
- **debug**: effective when debug mode enabled, see *Debug* section

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
}
```
- **include_all_keywords**: Requires that an email contain at least one keyword from *each* defined group to be considered a valid match
- **exclude_any_keywords**: Immediately rejects any email containing one or more of the specified keywords
- **order_id_patterns**: Defines regular expressions used to detect valid order id
- **domains**: Restricts processing to emails sent from approved sender domains only

## API Documentation

### Endpoint

#### New User
- **URL**: `/`
- **Method**: `POST`
- **Authentication**: HTTP Basic Authentication
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "bubble_user_id": "string"
}
```

#### Delete User
- **URL**: `/delete/`
- **Method**: `POST`
- **Authentication**: HTTP Basic Authentication
- **Content-Type**: `application/json`

- **Request Body**:
```json
{
  "bubble_user_id": "string"
}
```

#### Authentication

The endpoint is protected using **HTTP Basic Auth**.

- Username and password are validated server-side against values stored in `auth.json`
- Requests without valid credentials will receive `401 Unauthorized`


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

## Debug

Enable the debug mode with environmental variable *DEBUG*

On Linux, this can be ```export DEBUG=1```

Debug mode will do following things:

- The *startDate* and *endDate* in config will replace *defaultStartMonthsAgo* to decide the gmail query interval
- Detailed message info will be printed in log, including ```message_id, timestamp, subject, sender```, which of the 3 filters it has passed: ```domain, keyword, order id```, and whether it's blocked by ```excluding keywords```
- *maxWorkers* will be set to 1 to ensure correct log output
- For every email, the combined text, which is ```subject + html + text``` will be saved to folder *debug*. Timestamp in file name is the timestamp of this email
- The ```html``` section in payload sent to the downstream service will be saved to folder *sent*. The first timestamp in file name is the timestamp of this email, the second timestamp is the time it's sent to the downstream service
