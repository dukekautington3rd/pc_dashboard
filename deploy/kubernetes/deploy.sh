for deployment in backend-api.yaml cache-redis.yaml defenders-deployed.yaml frontend-dash.yaml postgres-edw.yaml; do
kubectl apply -f $deployment -n pc-dashboard
done
