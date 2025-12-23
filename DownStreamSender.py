import json
import time
import random
import string
import requests
from datetime import datetime, timezone

with open("config.json", "r") as f:
    config = json.load(f)
url = config["downstreamEndpoint"]

def send_payload(subject, sender, current_user, html, text, timestamp):
    CODE_LENGTH = 8
    dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
    iso_date = dt.isoformat().replace("+00:00", "Z")

    code = ''.join(random.choice(string.ascii_uppercase) for _ in range(CODE_LENGTH))
    
    formatted_subject = f"<<{current_user}>>||{code}|| {subject}"
    
    '''
        people inventing this hard coding is really a bitch
    '''
    payload = [
        {
            "email": {
                "headers": {
                    "delivered-to": "Delivered-To: testuser1.gr@gmail.com",
                    "received": "Received: from CY3PR08MB10672.namprd08.prod.outlook.com\r\n ([fe80::2c6c:2470:4af3:4647]) by CY3PR08MB10672.namprd08.prod.outlook.com\r\n ([fe80::2c6c:2470:4af3:4647%6]) with mapi id 15.20.9412.005; Sun, 7 Dec 2025\r\n 21:18:53 +0000",
                    "x-google-smtp-source": "X-Google-Smtp-Source: AGHT+IHyPTqKsqLC2Ib0EwsdUc4PeFnGESaA2yBBr+pb/L42UP28tz2zvhPJL6Fvl11RzvqrbSAI",
                    "x-received": "X-Received: by 2002:a05:6820:c87:b0:659:9a49:8e01 with SMTP id 006d021491bc7-6599a97bb3bmr2598834eaf.67.1765142340382;\r\n        Sun, 07 Dec 2025 13:19:00 -0800 (PST)",
                    "arc-seal": "ARC-Seal: i=1; a=rsa-sha256; s=arcselector10001; d=microsoft.com; cv=none;\r\n b=xR4/MGVkSb6z4v3ceo7xyGQD0A8gvKrnnkkzRS2qAJtRrsoKBGdLCCDD/36w4RmM75eesHz7w1mh+usEQS0tAH9jEd2MBE0mw4pTKvBiiXnoZ+bQb30wI9460I4uXftRWXaHFXCc8oHS8LqitQlKgEC/1lLqmItm7MKtsqcFY77704MkeU2Zi1tv5emt1+Cq9yB/PKyORY985koP75YpH5Dc/MzhC3Nq435/2LdDQ6SWKK5JA8rqLiKMeJnWy3vk1C5bH96/GFo9ELrrm9WXBQIa3MKvpqoBBsX3we56Lm8Yf6mB9v4DU7yx+brRM49DRBhKGhd4W86dITBe76uQpA==",
                    "arc-message-signature": "ARC-Message-Signature: i=1; a=rsa-sha256; c=relaxed/relaxed; d=microsoft.com;\r\n s=arcselector10001;\r\n h=From:Date:Subject:Message-ID:Content-Type:MIME-Version:X-MS-Exchange-AntiSpam-MessageData-ChunkCount:X-MS-Exchange-AntiSpam-MessageData-0:X-MS-Exchange-AntiSpam-MessageData-1;\r\n bh=SNuDP5eCj9AsZbZ5FNQBlxxiUT+KMOp2Fo+EWMYgWx4=;\r\n b=zT75J2UGYvke+2Gq1rrGJV8AJ58p9i8kfmBeq4AZdsUC+NftIpgqBYfpVu3h3zd74mGd6CwYGNJ0DKnmyHYKzOZSkemWfLUlNc63IcPU6K3LQuKqQWFB6XKL951TSJQv/vNHfi8MUDB9uzTIe9xjNZmkIimLzoXKaAHYMsq53wLLFLCJbCz6Q2r23P7HlUcdf8XsUiqsWmI2uYqdmxxBpw9hGcXCqnh7ZsbZ5w94M9DKdg/5Y8Opyf2V11rD9HpY/ZbZDuFhnhwey778urfmqe3AWVoVLCWLjW+wvq9bspLEzyXWWm7aSZ02tIcLx2SDVLcam2P9QH/BQ8cVoWcWxA==",
                    "arc-authentication-results": "ARC-Authentication-Results: i=1; mx.microsoft.com 1; spf=pass\r\n smtp.mailfrom=garde-robe.com; dmarc=pass action=none\r\n header.from=garde-robe.com; dkim=pass header.d=garde-robe.com; arc=none",
                    "return-path": "Return-Path: <receipt@garde-robe.com>",
                    "received-spf": "Received-SPF: pass (google.com: domain of receipt@garde-robe.com designates 148.163.129.52 as permitted sender) client-ip=148.163.129.52;",
                    "authentication-results": "authentication-results: dkim=none (message not signed)\r\n header.d=none;dmarc=none action=none header.from=garde-robe.com;",
                    "x-virus-scanned": "X-Virus-Scanned: Proofpoint Essentials engine",
                    "dkim-signature": "DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed; d=garde-robe.com;\r\n s=selector1;\r\n h=From:Date:Subject:Message-ID:Content-Type:MIME-Version:X-MS-Exchange-SenderADCheck;\r\n bh=SNuDP5eCj9AsZbZ5FNQBlxxiUT+KMOp2Fo+EWMYgWx4=;\r\n b=F4GuxsSO9Io11BcrZUhkYeWDfCDI/6ehV14qJSkV5vQVfVWkBLOcXHTEtdHuL900qIC/PDdueGqnJO0Wzt5oUHNLxX8H63EHw2Ug5wcX57oDlGj6QgvroKG+/yCDyD92Ab2RJIzTVgVDOXWCl65P+R+vfbuspu6ac7dhzn4UBAQM3MC+GjXoUHwYPe+CjQCWYpDQvEaHjEszqxw/yz6280zH9Yr0rCo+80XR6OitswV26ZpEcYHGy/zf3eU1Yi02LH1Jr3XHJSsO12MmcohqndMrFdrtLSPXIywCc6GjR9UsF74/9C6q82vcE9B0+N3EYARVd43XhXDTB7fJjcO2kw==",
                    "from": "From: Garde-Robe <receipt@garde-robe.com>",
                    "to": "To: \"testuser1.gr@gmail.com\" <testuser1.gr@gmail.com>",
                    "subject": "Subject:\r\n =?utf-8?B?PDxzYXJhaGZpbmRsYXkyQGdtYWlsLmNvbT4+fHxJS0ZUVkdJTnx8IEZ3ZDog?=\r\n =?utf-8?B?Vm90cmUgcmVjzKd1IGRlIFNlcGhvcmE=?=",
                    "thread-topic": "Thread-Topic:\r\n =?utf-8?B?PDxzYXJhaGZpbmRsYXkyQGdtYWlsLmNvbT4+fHxJS0ZUVkdJTnx8IEZ3ZDog?=\r\n =?utf-8?B?Vm90cmUgcmVjzKd1IGRlIFNlcGhvcmE=?=",
                    "thread-index": "Thread-Index: AQHcZ78Wt5UlSKaFNUmAtzkXP24cpQ==",
                    "importance": "Importance: low",
                    "x-priority": "X-Priority: 5",
                    "date": "Date: Sun, 7 Dec 2025 21:18:53 +0000",
                    "message-id": "Message-ID:\r\n <CY3PR08MB1067275442D6D09BB12B0038B8BA5A@CY3PR08MB10672.namprd08.prod.outlook.com>",
                    "accept-language": "Accept-Language: en-GB, en-US",
                    "content-language": "Content-Language: en-US",
                    "x-ms-has-attach": "X-MS-Has-Attach:",
                    "x-ms-tnef-correlator": "X-MS-TNEF-Correlator:",
                    "x-ms-mail-application": "x-ms-mail-application: Microsoft Power Automate; User-Agent:\r\n azure-logic-apps/1.0 (workflow 3631ef455ee44a8cb80b2829b7201387; version\r\n 08584434883116750226) microsoft-flow/1.0",
                    "x-ms-mail-operation-type": "x-ms-mail-operation-type: Send",
                    "x-ms-mail-environment-id": "x-ms-mail-environment-id: default-4127e910-9941-474f-b7fd-b0b1873951c5",
                    "x-ms-mail-workflow": "x-ms-mail-workflow: x-ms-workflow-name: 6cd87d5f-c6d2-4454-be93-fc1dff0f5d88;\r\n x-ms-workflow-run-id: 08584364645550695556687782625CU20;\r\n x-ms-client-request-id: 8d4b4916-ca0f-4320-84b9-ac2f2782e9e2;",
                    "x-ms-publictraffictype": "x-ms-publictraffictype: Email",
                    "x-ms-traffictypediagnostic": "x-ms-traffictypediagnostic: CY3PR08MB10672:EE_|DS4PR08MB10726:EE_",
                    "x-ms-office365-filtering-correlation-id": "x-ms-office365-filtering-correlation-id: 4e1fbea5-d1e0-4de5-0ce1-08de35d63928",
                    "x-ms-exchange-senderadcheck": "x-ms-exchange-senderadcheck: 1",
                    "x-ms-exchange-antispam-relay": "x-ms-exchange-antispam-relay: 0",
                    "x-microsoft-antispam": "x-microsoft-antispam:\r\n BCL:0;ARA:13230040|376014|366016|69100299015|1800799024|38070700021|8096899003;",
                    "x-microsoft-antispam-message-info": "x-microsoft-antispam-message-info:\r\n =?utf-8?B?d3RKTVFzaHphSHVCNmhxRU43cFNQNmF6bm1RK1pHRU80MUpKREdDZFRuQzB4?=\r\n =?utf-8?B?ZG8zVUtDeTJ3WnkyVm9peHc0M3VmT2pOaFZBQzlBQU11NnVzeitGbFRrcVJK?=\r\n =?utf-8?B?NElRckNMckFUQk9LY2FJcnVVVU9PZHgramtzRldwM1pQMFZlckFwVDM3cExa?=\r\n =?utf-8?B?cytpUDI2Nm1SdWNKT3R4c1NVWW5WTnpBOWFBc0tMV0JWbUFpOXNKNTZIOUdm?=\r\n =?utf-8?B?OWc5d1NqUzhQdS9vTE9Sc0crSU5TREZ3SXlOK1UvYmorRExvNW8rbVRVeEVR?=\r\n =?utf-8?B?Qlo4Z29lWXFxcWwxYTZLWm1JY2hQZTFtY1JzeVdOZEw0UTJQR0xub2p3dGE4?=\r\n =?utf-8?B?M1pnOVhUa2l3MkJRWkhxczRtMDFtb0RvNGJuei80cXlVV255WFFxc0tkVS90?=\r\n =?utf-8?B?ZitpNFlFblBaZ3lGT1Q4ajhLTmZtQjRuYmdzRXcxU0cwM1NyUFJXWm5qMHdR?=\r\n =?utf-8?B?MTJuUzNrTUFSU2swTG9JNHYyT3BwTTBDdTVmMnZIYm9kUi9ZTE94S3ErVzJx?=\r\n =?utf-8?B?UzhlbnN6SkRoY1B6SHVObUtkMUhRZHZHdzVuTVJuYzFabmgyc3l3d1FDNkdP?=\r\n =?utf-8?B?a0V4d1hRbFBGRjhpYmpMR3NOWmF6d0JaUXlTWmsySWVCTHRjbzBFMWxCRGQr?=\r\n =?utf-8?B?Y0hxYW4vSlNic1ZXLzF1bHV1R09ZaGJyak5henB2VWdGT2FSSVplME56YWp1?=\r\n =?utf-8?B?RHRjK3lWaUdCZzAvY0dkaExLNytvMHZSdVhuVVcrQjhLQWNOV1VXVGRzMVBy?=\r\n =?utf-8?B?MTNtRlVXdklyeHp3bEtGczhxL2tsL05YMXkvaUxGUEp1SFdkUXc5ZGZQcUF5?=\r\n =?utf-8?B?M2NuUnJQSkJYeGtKL2FWSFRtSjdaTG1JYUxCZUU2cFJGaWJjSFJDU3hTbG9O?=\r\n =?utf-8?B?NlZ0ZWRNaUVPNkhBR0RTbDRZRU0rTFZtUFRaU1ZkanF2UldQQi93a2tMR1p2?=\r\n =?utf-8?B?Wk9xQ1R3QkxqeUxHZVdFQTMzWjViY3hndWtVUTRBL2Y1RzRadkVaeVl0U212?=\r\n =?utf-8?B?eVVTL1k0MTNuNHZrRlpVUkZQVmMweUszVDlsMmI0dlJVdEpqVEFhTS9ZWlc0?=\r\n =?utf-8?B?b01wMTRTTHBKaEhoZTYvZ25FOVV3TVlBaTNZdVM1RFlJaldKYkVBUitTU1BH?=\r\n =?utf-8?B?RHpCTkFndG53bkJOcGE3QUVscG5ZdCtVL1JQZlY1dEF1T2dSTml2MStMWjV1?=\r\n =?utf-8?B?eHBWZ29KdGEwb3NNWGV5Ui9BUFZYL0xucnExSVI5YVZrVFZROUVsUU1WOStl?=\r\n =?utf-8?B?dUxVRDk1Y2tZbnBpQlFQVVNJTTNrT1VxMnhIZE5IanM1d0JoUjlmSHAxZEJM?=\r\n =?utf-8?B?Wktnb2JVbWc0dmZjN1VRL012UXZDb2lkNWdkNVFmS0ZnenIyMnRNcG50bUNO?=\r\n =?utf-8?B?OWJWQ1VMOCtjY0ZDZlZwc29weWtBMXhwa3N0MkN4UkE5V2N6RU1Qelg2UVBF?=\r\n =?utf-8?B?OGtNcjcvRVZtYjdoSGFnRXM0K1VxdVppT1V1MW9JTW5FdHZsakJUSmtHREV6?=\r\n =?utf-8?B?ZjV0cnFmWnRBbXMrRzdTTFlqZTdjSytmcnpYcCtMZ0dpS3cvVXVNZGxVSG9R?=\r\n =?utf-8?B?ZzNHVFZUeStLQlYwR2NFYUNHK0VVUm5PejEzUlpFR0tsVkI5eExnV3dTeVRS?=\r\n =?utf-8?B?RjAza2ZjT1QzSFJURERxS3FjZURQN1RWQ2JIREliWHZWSWlzZ0VITnp2UUtx?=\r\n =?utf-8?B?RDVBZWRmZEhYWFZXT25UaXNFbi9wNFBhVjZuNEV2T2ZtY013dkpEdEVsZ1dS?=\r\n =?utf-8?B?RTJtWGtaK0R6MFZaQSs3L3d6c3RYV1pySERvNzQ2M0pUMkdKWU1hVXdnWXlw?=\r\n =?utf-8?B?cDczUUxPMDE1azV1RG9EZmRheHd1TU4vb0Q2dTYyeTA4eFB2YWJOdG43Wm51?=\r\n =?utf-8?B?Yzh6MlNEVy80bnpYTzlEUHpFclZJU014Y0tTWmdrRnZQSnZadGlsWHVTS2F3?=\r\n =?utf-8?B?WTJFa3JLb1BjOWcxR0xUQzF2WXFLeU1wbmg3TUdwNnZJY0l4RUdPY2hDTEw0?=\r\n =?utf-8?B?d2ptMUtpZUtRPT0=?=",
                    "x-forefront-antispam-report": "x-forefront-antispam-report:\r\n CIP:255.255.255.255;CTRY:;LANG:fr;SCL:1;SRV:;IPV:NLI;SFV:NSPM;H:CY3PR08MB10672.namprd08.prod.outlook.com;PTR:;CAT:NONE;SFS:(13230040)(376014)(366016)(69100299015)(1800799024)(38070700021)(8096899003);DIR:OUT;SFP:1102;",
                    "x-ms-exchange-antispam-messagedata-chunkcount": "x-ms-exchange-antispam-messagedata-chunkcount: 1",
                    "x-ms-exchange-antispam-messagedata-0": "x-ms-exchange-antispam-messagedata-0:\r\n =?utf-8?B?eG8rdVl2dVNlNUUzeC9HZ2twcStzSVNoYnZseHIrT2VDdUV3Nmdoc0VzSCtI?=\r\n =?utf-8?B?N1R0VmpWNWpMUmNUWVBkVHpEdDRVclEvZko1dnFVR0VIa0dkR09Ka1MrelVH?=\r\n =?utf-8?B?NHFYVjQ2aHFlV09sdTdYblRnbi9CeEl0dWJWU3MwTzFpTkRKb3lQUWRGRU4r?=\r\n =?utf-8?B?UUcwTkR6WnE0S2dQMElkN2VUZGIyYlJKczdzOW5jQ3cyNkQ1ajRxSkNnYTZN?=\r\n =?utf-8?B?SktMdVlSMWdUeWwzaTcxSWtadlVEK2VETjM1RlI2VUgzUW9heHpxblRXMk1H?=\r\n =?utf-8?B?MEFNOEo1Q0o0YTJodXZWWDkyaE5UcGl1d0tRakNaSHdHNjhrRk1WSERMSU11?=\r\n =?utf-8?B?R2hxSHUxK3BndzZiTUV4ZnhJc0NPdmtoN3hQd0ZoQUJQZ0V0RlYybU80Z1Nq?=\r\n =?utf-8?B?dFVDdzluRlhnNFhQOGRmWk8wM3hvSlFtNVAzNk95NXpmNW02WjVGOVhqMXBw?=\r\n =?utf-8?B?eTV5ejlNQUYyd1pubmIzVE9XMU9tVUxGOW5COWU4bkZqUDl6aDBhazdjSUg1?=\r\n =?utf-8?B?YlR6eWVCNDhQMXZBOXo2TU9NT2REQkhmdVlTM0JKMFNHVEFoMU5wd1M1S3hM?=\r\n =?utf-8?B?a29wTjBMdllWMWp0VjY2NFJyVU40eDRNWmVpZEw3c3pVZVlhbUZpU0dkZGRw?=\r\n =?utf-8?B?aWkxNzIzaFBmVjBhZC9jWGdObDhENkJzUUR5U1RmZ244clRUL2lldHg0K25L?=\r\n =?utf-8?B?Z2Q5Y2hGSEtVdEFneWVXdmt2RjRNcGt6eHRhMWxPRkFhaUl0dFovWU1Tblhs?=\r\n =?utf-8?B?bjRZdnZwWEpkSm56cU0vNnppODZxV0hnSm03UGZ0eEs1M00zOFl2UHJ1RFIx?=\r\n =?utf-8?B?Mzc5aWlmQm1NYm51OHhHQUpPL1VjS3BWWEl1UytGYjhNSkFjcUR1OWdYbDcz?=\r\n =?utf-8?B?QS9uK3ZpK2diaG5hVkVQSHY0T3UrdHdCNDJ3c0dNRy9XYmlKTzlzU3dkSlps?=\r\n =?utf-8?B?Z2hCQzZ5ZTBKT3ROMkJZT0l6Nm1kQjlRdU9pcUc1bS9WTDlpMFdSR0dLdVhz?=\r\n =?utf-8?B?S0VPZFVmdkNiM0FlOXZWK1Jqd1JwRklZUDBrWVRoZUxVUFFIZllqVCtvWU1h?=\r\n =?utf-8?B?aWdLSzA3YmJSSldGUzg1RGxTTm82cWhNNjZaQmx0TjZnZjh3bTdUQ25LOWVX?=\r\n =?utf-8?B?ekg1ajFCT3dDVGF3NUhXcE94T2RqdkRVSUlkVU8yVThRT2Mxcjhsc0dLN0VN?=\r\n =?utf-8?B?TGRoSHNXbjltYk0yRHoxWHNFTTFla1J2dXZlMFVRa2d3TlQ5V0gvTU14WjJ5?=\r\n =?utf-8?B?Q05wclgvbmxSZUszdGM5RDBWcFVOWis0MmxVYUVlT3RjSEd3Z0FqUGhONDdp?=\r\n =?utf-8?B?emU5M1lPV21hV21OelJncEYweDkrMDJnY1hIelVFSHVTelFxa3B0UFFxNzV0?=\r\n =?utf-8?B?eEp6OFFBV1U5WVVaaGlweTlTTWl3UU44b2hpeWluVHh1NjRPYit4UnU2Qnk3?=\r\n =?utf-8?B?VTBpUmwyVGtVVk1semhSUUlqOU91ck1MVGhqUnQ2UDVqYUVOVjV6MEtJRW9h?=\r\n =?utf-8?B?ajVDMDArOGNjYVo3Y0lWcTBDbHhYSU05MGhZazVLazRXL1gwYTVYQlpXSTBU?=\r\n =?utf-8?B?UUgzNEFqQVNRenZKd0RqOVNiMGg1d2orSDRLQUpwMG1HNmc1QURTd25ab3Rt?=\r\n =?utf-8?B?bHgwdTlaZUZic2xEYTBtd0JsS0NITjdMWnhuU1JaY3dFMnJXOEc4ZzVZVm45?=\r\n =?utf-8?B?VFlBV05YeXdua2FFc2EzZUFaK1N4c05EeGJ3WlJ6R2dkUjdKZXAvZ0YwYnJu?=\r\n =?utf-8?B?WEJVejhSMml0OEk3aFZQbFM3Rk4zNUF0RGlzc204MFJwN2NEQnUrWWRwUEY4?=\r\n =?utf-8?B?Q3FjMExyWmI4d29KeWcwdXlXbyt3QTJpTXVQMHVUaDVZWGtudUFkZXFiN1or?=\r\n =?utf-8?B?d05qL0F1VFBpTURMWC85ZmJHYlpITURneHdLRUNFTGdoSE9aQjRLdE15am5w?=\r\n =?utf-8?B?RDdWc1pYZURBVExHTGxXY1NvVHFhWHQ1R3RSWlEvU2ZIRWp4eVJlN1dac0hq?=\r\n =?utf-8?B?bzZBM253c0RwcGlTRlQ2M1YwRjdBTlVvRkpQbWZld1dadjZUQlJGK2wvRTd2?=\r\n =?utf-8?B?Ni9NWE9mMitXQmlLMWdSTXd0YXhtMnhQL01aRUlIUXRwYkQ3OVB4TWpGUmsz?=\r\n =?utf-8?Q?BIjkvN5iW6gDHZa5JhUhpqE6N?=",
                    "content-type": "Content-Type: multipart/alternative;\r\n\tboundary=\"_000_CY3PR08MB1067275442D6D09BB12B0038B8BA5ACY3PR08MB10672na_\"",
                    "mime-version": "MIME-Version: 1.0",
                    "x-originatororg": "X-OriginatorOrg: garde-robe.com",
                    "x-ms-exchange-crosstenant-authas": "X-MS-Exchange-CrossTenant-AuthAs: Internal",
                    "x-ms-exchange-crosstenant-authsource": "X-MS-Exchange-CrossTenant-AuthSource: CY3PR08MB10672.namprd08.prod.outlook.com",
                    "x-ms-exchange-crosstenant-network-message-id": "X-MS-Exchange-CrossTenant-Network-Message-Id: 4e1fbea5-d1e0-4de5-0ce1-08de35d63928",
                    "x-ms-exchange-crosstenant-originalarrivaltime": "X-MS-Exchange-CrossTenant-originalarrivaltime: 07 Dec 2025 21:18:53.0801\r\n (UTC)",
                    "x-ms-exchange-crosstenant-fromentityheader": "X-MS-Exchange-CrossTenant-fromentityheader: Hosted",
                    "x-ms-exchange-crosstenant-id": "X-MS-Exchange-CrossTenant-id: 4127e910-9941-474f-b7fd-b0b1873951c5",
                    "x-ms-exchange-crosstenant-mailboxtype": "X-MS-Exchange-CrossTenant-mailboxtype: HOSTED",
                    "x-ms-exchange-crosstenant-userprincipalname": "X-MS-Exchange-CrossTenant-userprincipalname: stRZlgtKfEXwSznM/QiXPj8PxBAdo6FT8E+ZioHy0wETcOPbaAXVbsY03DkcxwYqaYezoeE66zQYlbGvjHJwgw==",
                    "x-ms-exchange-transport-crosstenantheadersstamped": "X-MS-Exchange-Transport-CrossTenantHeadersStamped: DS4PR08MB10726",
                    "x-mdid": "X-MDID: 1765142336-0BMZodsRrl3q",
                    "x-ppe-stack": "X-PPE-STACK: {\"stack\":\"us4\"}",
                    "x-mdid-o": "X-MDID-O:\r\n us4;ut7;1765142336;0BMZodsRrl3q;<receipt@garde-robe.com>;aabb64fd532122a62f3350510091d3b4",
                    "x-ppe-trusted": "X-PPE-TRUSTED: V=1;DIR=OUT;"
                },
                "html": html,
                "text": text,
                "textAsHtml": html,
                "subject": formatted_subject,
                "date": iso_date,
                "to": {
                "value": [
                    {
                        "address": "testuser1.gr@gmail.com",
                        "name": ""
                    }
                ],
                "html": "<span class=\"mp_address_group\"><a href=\"mailto:testuser1.gr@gmail.com\" class=\"mp_address_email\">testuser1.gr@gmail.com</a></span>",
                "text": "testuser1.gr@gmail.com"
                },
                "from": {
                    "value": [
                        {
                            "address": "receipt@garde-robe.com",
                            "name": "Garde-Robe"
                        }
                    ],
                    "html": "<span class=\"mp_address_group\"><span class=\"mp_address_name\">Garde-Robe</span> &lt;<a href=\"mailto:receipt@garde-robe.com\" class=\"mp_address_email\">receipt@garde-robe.com</a>&gt;</span>",
                    "text": "\"Garde-Robe\" <receipt@garde-robe.com>"
                },
                "messageId": "<CY3PR08MB1067275442D6D09BB12B0038B8BA5A@CY3PR08MB10672.namprd08.prod.outlook.com>",
                "attributes": {
                    "uid": 1390
                }
            }
        }
    ]

    with open(f"payload{timestamp}-{int(time.time())}.html", "w") as f:
        f.write(html)
    
    response = requests.post(url, json=payload)

    return response.status_code, response.text
