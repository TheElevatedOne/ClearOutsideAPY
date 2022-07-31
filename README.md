# ClearOutsideCustomAPI
**Webscraper for ClearOutside.com**
<br>
Webscrapes clearoutside depending on *your settings* and gives you output in *json.*
<br>
To Open Settings: `clearoutside-api -s`
To Update JSON: `clearoutside-api -u`
<br>
In settings, location is changed by **pressing enter** after typing the city in... Please change it, it will show errors. Will fix it later i'm so sleepy...
<br>
#### Settings Window
![Window](https://i.imgur.com/JbKPv7q.png)
<br>
#### JSON Preview:
```
[
    {
        "Day": "Sunday",
        "Date": "31",
        "Weather": {
            "12": {
                "Status": "Bad",
                "Total-Cloud": "84%",
                "Rain-Probability": "100%",
                "Wind-Speed": "35%",
                "Temperature": "24.1 kmh",
                "Humidity": "18"
            },
            "13": {
                "Status": "Bad",
                "Total-Cloud": "78%",
                "Rain-Probability": "98%",
                "Wind-Speed": "37%",
                "Temperature": "24.1 kmh",
                "Humidity": "18"
            },
            
            .
            .
            .
            
            "10": {
                "Status": "Bad",
                "Total-Cloud": "64%",
                "Rain-Probability": "89%",
                "Wind-Speed": "0%",
                "Temperature": "6.4 kmh",
                "Humidity": "22"
            },
            "11": {
                "Status": "Bad",
                "Total-Cloud": "59%",
                "Rain-Probability": "95%",
                "Wind-Speed": "0%",
                "Temperature": "9.7 kmh",
                "Humidity": "24"
            }
        },
        "Celestial-Time": [
            "Sun - Rise: 05:23, Set: 20:25, Transit: 12:54",
            " Moon - Rise: 08:57, Set: 22:04",
            "Civil Dark: 21:02 - 04:47",
            "Nautical Dark: 21:49 - 04:00",
            "Astro Dark: 22:48 - 03:02"
        ]
    },
```
