https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/quickstart-python describes how to stand up the local test kit using the 

```bash
teamsapptester
```



You can use the `dev tunnels`. Please follow [Create and host a dev tunnel](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started?tabs=windows) and host the tunnel with anonymous user access command as shown below:

   ```bash
   devtunnel host -p 3978 --allow-anonymous
   ```

Go to the bot service and use the dev tunnel URL (e.g. `https://<your-tunnel-id>.devtunnels.ms`) as the messaging endpoint for your bot in the format:

```https://<your-tunnel-id>.devtunnels.ms/api/messages
```

Zip files with:
```bash
Compress-Archive -Path manifest.json,color.png,outline.png -DestinationPath ..\teamsapp.zip -Force
```


