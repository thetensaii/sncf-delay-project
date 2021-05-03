import requests
import urllib.request
import json
import folium, branca
from datetime import date, timedelta
import matplotlib.pyplot as plt
import tkinter

URL = "https://api.sncf.com/v1/coverage/sncf/disruptions"
TOKEN_SNCF = "a3e13cfc-85f7-4f92-bf86-3bd444febf56"

class MySNCFApp():
    def __init__(self):
        self.initMap()
        self.disruptions = []
        self.nb_journey_by_points = {}
        self.tab_retard_max = []

    def initMap(self):
        france_coords = (46.764136346626124,2.213749000000007)
        self.map = folium.Map(location=france_coords, tiles='OpenStreetMap', zoom_start=6)
        self.cm = branca.colormap.LinearColormap(['yellow', 'red',"black"], vmin=1, vmax=180, caption="Retard Max (en min)")
        self.map.add_child(self.cm)

    def getDatas(self,date):
        proxy_address = 'http://147.215.1.189:3128/' #ESIEE
        proxy_handler = urllib.request.ProxyHandler({'http': proxy_address})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

        # Récupération des données de 1000 trains à l'aide d'une requête HTTPS
        response = requests.get(
            'https://api.sncf.com/v1/coverage/sncf/disruptions', 
            headers={'Authorization': 'a3e13cfc-85f7-4f92-bf86-3bd444febf56'},
            params = {"since" : date+"T000000", "until" : date+"T235959", "count": 2000 }
        )
        self.datas = response.text
        
    def setDisruptionsList(self):
        # Mettre dans un dictionnaire/Tableau l'ensemble des retards avec la station de début, la station d'arrivée, le motif, calculé le retard total
        data = json.loads(self.datas)
        self.disruptions = []

        for d in data["disruptions"] :
            if d["severity"]["name"] != "trip delayed":
                continue
            
            # Initilisation d'un train
            disruption = {
                "motif" : "",
                "first_station_name" : "",
                "last_station_name" : "",
                "stop_points" :[],
                "retard_max" : 0,
                "retard_depart" : [],
                "retard_arrivee" : []
            }

            # Vérifie s'il y a bien une station en retard
            first_station = False

            # Permet de récupérer le motif du retard
            disruption["motif"] = d.get("messages", "null")
            if disruption["motif"] != "null":
                disruption["motif"] = disruption["motif"][0]["text"]
            else :
                disruption["motif"] = d["impacted_objects"][0]["impacted_stops"][0]["cause"]
                

            for station in d["impacted_objects"][0]["impacted_stops"] :
                # Recuperation de la première station avec un retard
                if station["stop_time_effect"] == "delayed" and not(first_station):
                    disruption["first_station_name"] = station["stop_point"]["label"]
                    base_departure_time = station.get("base_departure_time", "null")
                    amended_departure_time = station.get("amended_departure_time", "null")

                    # S'il n'y a pas de données concernant l'horaire on passe à la station suivante
                    if (base_departure_time == "null" or amended_departure_time == "null"):
                        continue

                    disruption["retard_depart"].append(base_departure_time)
                    disruption["retard_depart"].append(amended_departure_time)
                    retard = self.calculRetard(station["base_departure_time"], station["amended_departure_time"])
                    first_station = True
                    
                # Recupération de la dernière station avec un retard 
                arrivee_prevu = station.get("base_arrival_time","null")
                arrivee_reelle = station.get("amended_arrival_time","null")
                if(arrivee_prevu == "null" or arrivee_reelle == "null"):
                    continue

                disruption["last_station_name"] = station["stop_point"]["label"]
                disruption["retard_arrivee"].clear()
                disruption["retard_arrivee"].append(arrivee_prevu)
                disruption["retard_arrivee"].append(arrivee_reelle)

                # Tableau de coordonées [lat,lon] de chaque stations concernées + calcul retard max
                if first_station != False:
                    stop_point = {
                        "coord" : "",
                        "label" : ""
                    }
                    stop_point["coord"] =  [ float(station["stop_point"]["coord"]["lat"]), float(station["stop_point"]["coord"]["lon"]) ]
                    stop_point["label"] = station["stop_point"]["label"]

                    disruption["stop_points"].append(stop_point) 

                    retard = self.calculRetard(disruption["retard_arrivee"][0], disruption["retard_arrivee"][1])
                    if (retard > disruption["retard_max"]):
                        disruption["retard_max"] = retard

            # En prévention des possibles erreurs de la sncf
            if(first_station != False and disruption["retard_max"]  != 0) :
                self.disruptions.append(disruption)


    def calculRetard(self,raw_prevu, raw_reelle):
        heure_prevu = int(raw_prevu[:2])
        minute_prevu = int(raw_prevu[2:4])

        heure_reelle = int(raw_reelle[:2])
        minute_reelle = int(raw_reelle[2:4])

        retard = 60 * (heure_reelle - heure_prevu)
        if(heure_prevu > heure_reelle):
            retard += 60 * 24
        retard += minute_reelle - minute_prevu

        return retard

    def fillMap(self):
        self.nb_journey_by_points = {}
        self.tab_retard_max = []
        for disruption in self.disruptions:
            self.addDisruptionToMap(disruption)

    def saveMap(self):
        self.map.save(outfile = "index.html")

    def printHist(self, title, datas, intervalles, xlabel, ylabel):
        plt.hist(datas, bins = intervalles, edgecolor = "black")
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.show()

    def addDisruptionToMap(self,disruption):
        # Gestion de la popup
        text = "De : <b>"+disruption["first_station_name"] + "</b> à <b>"+disruption["last_station_name"] + "</b><br>"
        text += "Motif : <b>" + disruption["motif"] + "</b><br>"
        text += "Départ <i><s>" + disruption["retard_depart"][0][0:2] + ":" + disruption["retard_depart"][0][2:4] + "</s></i> -> <i>" + disruption["retard_depart"][1][0:2] + ":" + disruption["retard_depart"][1][2:4] + "</i><br>"
        text += "Arrivée <i><s>" + disruption["retard_arrivee"][0][0:2] + ":" + disruption["retard_arrivee"][0][2:4] + "</s></i> -> <i>" + disruption["retard_arrivee"][1][0:2] + ":" + disruption["retard_arrivee"][1][2:4] + "</i><br>"
        text += "Plus grand retard sur ce trajet : <b>"+str(disruption["retard_max"])+"</b> min"
        iframe = folium.IFrame(html=text,width=500, height=130)
        popup = folium.Popup(iframe,max_width=750)

        coords = []
        self.tab_retard_max.append(disruption["retard_max"])
        for stop_point in disruption["stop_points"]:
            coords.append(stop_point["coord"])
            if stop_point["label"] not in self.nb_journey_by_points.keys():
                self.nb_journey_by_points[stop_point["label"]] = 0
            self.nb_journey_by_points[stop_point["label"]] += 1
        folium.PolyLine(coords, popup = popup, color=self.cm(disruption["retard_max"]), weight=5, opacity=1).add_to(self.map)

    def generateHists(self):
        intervalles = list(range(0,30,3))
        self.printHist("Nombre de stations par nombre de trains\n en retards passé par celle-ci", 
            self.nb_journey_by_points.values(), 
            intervalles, 
            "Nombre de trains",
            "Nombre de stations"
            )
            
        self.printHist("Nombre de trains par temps de retard", 
            self.tab_retard_max, 
            40, 
            "Retard en min",
            "Nombre de trains"
            )

    def createSchemas(self,date):
        self.getDatas(date)
        self.setDisruptionsList()
        self.fillMap()
        self.saveMap()
        self.generateHists()


def main():
    app = MySNCFApp()
    yesterday = date.today() - timedelta(1)
    yesterday_date = yesterday.strftime("%Y%m%d")
    app.createSchemas(yesterday_date)

    


if __name__ == "__main__":
    main()