# =============================================================================
# Deployment Script - Python Voice Agent
# Local Docker or Azure Container Apps
# Voice Agent with Voice Live API and Cosmos DB
# =============================================================================

# Variables - UPDATE THESE FOR AZURE DEPLOYMENT
$RESOURCE_GROUP = "rg-voice-agent"
$LOCATION = "swedencentral"
$ENVIRONMENT_NAME = "voice-agent-env"
$CONTAINER_APP_NAME = "voice-agent-python"
$ACR_NAME = "acrvoiceagentmovistar"  # Must be globally unique, lowercase
$IMAGE_NAME = "voice-agent-python"
$IMAGE_TAG = "v$(Get-Date -Format 'yyyyMMdd-HHmmss')"  # Unique tag with timestamp
$LOCAL_PORT = 8081
$ENV_FILE = ".env"
$DOCKERFILE = "Dockerfile.python"

# =============================================================================
# Ask user for deployment target
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Voice Agent Python Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Where do you want to deploy?" -ForegroundColor Yellow
Write-Host "  1. Local Docker Desktop (for testing)"
Write-Host "  2. Azure Container Apps (for production)"
Write-Host ""
$choice = Read-Host "Enter your choice (1 or 2)"

# =============================================================================
# OPTION 1: Local Docker Desktop
# =============================================================================
if ($choice -eq "1") {
    Write-Host ""
    Write-Host "=== Deploying to Local Docker Desktop ===" -ForegroundColor Green
    Write-Host ""

    # Check if .env file exists
    if (-not (Test-Path $ENV_FILE)) {
        Write-Host "ERROR: .env file not found!" -ForegroundColor Red
        Write-Host "Please create a .env file with the required environment variables." -ForegroundColor Yellow
        exit 1
    }

    # Stop and remove existing container if running
    Write-Host "Stopping existing container (if any)..." -ForegroundColor Cyan
    docker stop $IMAGE_NAME 2>$null
    docker rm $IMAGE_NAME 2>$null

    # Build the Docker image (--no-cache ensures all changes are applied)
    Write-Host "Building Docker image (no cache)..." -ForegroundColor Cyan
    docker build --no-cache -t "${IMAGE_NAME}:${IMAGE_TAG}" -f $DOCKERFILE .

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker build failed!" -ForegroundColor Red
        exit 1
    }

    # Run the container with --env-file
    Write-Host "Starting container with .env file..." -ForegroundColor Cyan
    docker run -d `
        --name $IMAGE_NAME `
        -p "${LOCAL_PORT}:8081" `
        --env-file $ENV_FILE `
        "${IMAGE_NAME}:${IMAGE_TAG}"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to start container!" -ForegroundColor Red
        exit 1
    }

    # Wait for container to start
    Start-Sleep -Seconds 3

    # Check if container is running
    $containerStatus = docker ps --filter "name=$IMAGE_NAME" --format "{{.Status}}"
    if ($containerStatus) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  Container started successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "URL for Simulator:" -ForegroundColor Yellow
        Write-Host "  ws://localhost:$LOCAL_PORT" -ForegroundColor White
        Write-Host ""
        Write-Host "Health Check:" -ForegroundColor Yellow
        Write-Host "  http://localhost:$LOCAL_PORT/health" -ForegroundColor White
        Write-Host ""
        Write-Host "--- Useful Commands ---" -ForegroundColor Magenta
        Write-Host "View logs:     docker logs -f $IMAGE_NAME"
        Write-Host "Stop:          docker stop $IMAGE_NAME"
        Write-Host "Restart:       docker restart $IMAGE_NAME"
        Write-Host "Remove:        docker rm -f $IMAGE_NAME"
        Write-Host ""
        
        # Test health endpoint
        Write-Host "Testing health endpoint..." -ForegroundColor Cyan
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$LOCAL_PORT/health" -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Host "Health check: OK" -ForegroundColor Green
            }
        } catch {
            Write-Host "Health check: Waiting for server to be ready..." -ForegroundColor Yellow
            Write-Host "Run 'docker logs $IMAGE_NAME' to see startup logs" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Container failed to start. Check logs with: docker logs $IMAGE_NAME" -ForegroundColor Red
    }
}

# =============================================================================
# OPTION 2: Azure Container Apps
# =============================================================================
elseif ($choice -eq "2") {
    Write-Host ""
    Write-Host "=== Deploying to Azure Container Apps ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Image tag: $IMAGE_TAG" -ForegroundColor Cyan
    Write-Host ""
    
    # Ask if user wants to skip steps
    Write-Host "Do you want to skip any completed steps?" -ForegroundColor Yellow
    Write-Host "  0. Run all steps (default)"
    Write-Host "  1. Skip to Step 2 (ACR) - Resource Group exists"
    Write-Host "  2. Skip to Step 3 (Docker) - ACR exists"
    Write-Host "  3. Skip to Step 4 (Environment) - Image pushed"
    Write-Host "  4. Skip to Step 5 (Env vars) - Environment exists"
    Write-Host "  5. Skip to Step 6 (Container App) - Ready to create app"
    Write-Host "  6. Skip to Step 7 (Get URL) - App exists"
    Write-Host ""
    $startStep = Read-Host "Enter step to start from (0-6, default 0)"
    if (-not $startStep) { $startStep = "0" }
    $startStep = [int]$startStep

    # Helper function to check command result
    function Test-AzCommandSuccess {
        param([string]$StepName)
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: $StepName failed with exit code $LASTEXITCODE" -ForegroundColor Red
            Write-Host "Please fix the issue and run the script again." -ForegroundColor Yellow
            exit 1
        }
        Write-Host "OK: $StepName completed successfully" -ForegroundColor Green
    }

    # Check if .env file exists
    if (-not (Test-Path $ENV_FILE)) {
        Write-Host "ERROR: .env file not found!" -ForegroundColor Red
        Write-Host "Please create a .env file with the required environment variables." -ForegroundColor Yellow
        exit 1
    }

    # Read .env file and parse variables
    Write-Host "Reading environment variables from .env file..." -ForegroundColor Cyan
    $envVars = @{}
    $secretVars = @("AZURE_VOICE_LIVE_API_KEY", "COSMOS_KEY", "OPENAI_API_KEY", "DEEPGRAM_API_KEY")
    
    Get-Content $ENV_FILE | ForEach-Object {
        # Skip comments and empty lines
        if ($_ -match "^\s*#" -or $_ -match "^\s*$") { return }
        
        # Parse KEY=VALUE (only split on first =)
        if ($_ -match "^([^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            if ($value -and $value -ne "" -and -not $value.StartsWith("<")) {
                $envVars[$key] = $value
            }
        }
    }

    Write-Host "Found $($envVars.Count) environment variables" -ForegroundColor Gray

    # Step 1: Check Resource Group state and create if needed
    if ($startStep -le 0) {
        Write-Host ""
        Write-Host "[Step 1/7] Checking Resource Group..." -ForegroundColor Cyan
        
        $rgExists = az group exists --name $RESOURCE_GROUP 2>$null
        if ($rgExists -eq "true") {
            $rgState = az group show --name $RESOURCE_GROUP --query "properties.provisioningState" -o tsv 2>$null
            if ($rgState -eq "Deleting") {
                Write-Host "Resource Group '$RESOURCE_GROUP' is being deleted. Waiting for deletion to complete..." -ForegroundColor Yellow
                $maxWait = 300
                $waited = 0
                while ($waited -lt $maxWait) {
                    Start-Sleep -Seconds 10
                    $waited += 10
                    $stillExists = az group exists --name $RESOURCE_GROUP 2>$null
                    if ($stillExists -ne "true") {
                        Write-Host "Resource Group deleted." -ForegroundColor Green
                        break
                    }
                    Write-Host "  Still deleting... ($waited seconds)" -ForegroundColor Gray
                }
                if ($waited -ge $maxWait) {
                    Write-Host "ERROR: Resource Group deletion is taking too long. Please wait and try again." -ForegroundColor Red
                    exit 1
                }
            } else {
                Write-Host "Resource Group '$RESOURCE_GROUP' already exists (state: $rgState)" -ForegroundColor Gray
            }
        }
        
        Write-Host "Creating Resource Group..." -ForegroundColor Cyan
        az group create --name $RESOURCE_GROUP --location $LOCATION --output none
        Test-AzCommandSuccess "Resource Group creation"
    } else {
        Write-Host "[Step 1/7] Skipped (Resource Group)" -ForegroundColor Gray
    }

    # Step 2: Create Azure Container Registry
    if ($startStep -le 1) {
        Write-Host ""
        Write-Host "[Step 2/7] Creating Azure Container Registry..." -ForegroundColor Cyan
        
        $acrExists = az acr show --name $ACR_NAME --query "name" -o tsv 2>$null
        if ($acrExists) {
            Write-Host "ACR '$ACR_NAME' already exists, skipping creation" -ForegroundColor Gray
        } else {
            az acr create `
                --resource-group $RESOURCE_GROUP `
                --name $ACR_NAME `
                --sku Basic `
                --admin-enabled true `
                --output none
            Test-AzCommandSuccess "ACR creation"
        }
    } else {
        Write-Host "[Step 2/7] Skipped (ACR)" -ForegroundColor Gray
    }

    # Get ACR credentials (always needed)
    Write-Host "Getting ACR credentials..." -ForegroundColor Gray
    $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv
    $ACR_USERNAME = az acr credential show --name $ACR_NAME --query username -o tsv
    $ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
    
    if (-not $ACR_LOGIN_SERVER -or -not $ACR_USERNAME -or -not $ACR_PASSWORD) {
        Write-Host "ERROR: Failed to get ACR credentials" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: ACR credentials retrieved ($ACR_LOGIN_SERVER)" -ForegroundColor Green

    # Step 3: Build and Push Docker Image
    if ($startStep -le 2) {
        Write-Host ""
        Write-Host "[Step 3/7] Building and pushing Docker image..." -ForegroundColor Cyan
        
        az acr login --name $ACR_NAME
        Test-AzCommandSuccess "ACR login"
        
        docker build --no-cache -t "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" -f $DOCKERFILE .
        Test-AzCommandSuccess "Docker build"
        
        docker push "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
        Test-AzCommandSuccess "Docker push"
    } else {
        Write-Host "[Step 3/7] Skipped (Docker build/push)" -ForegroundColor Gray
    }

    # Step 4: Create Container Apps Environment
    if ($startStep -le 3) {
        Write-Host ""
        Write-Host "[Step 4/7] Creating Container Apps Environment..." -ForegroundColor Cyan
    
        $envExists = az containerapp env show --name $ENVIRONMENT_NAME --resource-group $RESOURCE_GROUP --query "name" -o tsv 2>$null
        if ($envExists) {
            Write-Host "Container Apps Environment '$ENVIRONMENT_NAME' already exists, skipping creation" -ForegroundColor Gray
        } else {
            az containerapp env create `
                --name $ENVIRONMENT_NAME `
                --resource-group $RESOURCE_GROUP `
                --location $LOCATION `
                --output none
            Test-AzCommandSuccess "Container Apps Environment creation"
        }
    } else {
        Write-Host "[Step 4/7] Skipped (Container Apps Environment)" -ForegroundColor Gray
    }

    # Step 5: Build env-vars and secrets strings
    Write-Host ""
    Write-Host "[Step 5/7] Preparing environment variables and secrets..." -ForegroundColor Cyan
    
    function ConvertTo-YamlSafeString {
        param([string]$Value)
        if ($Value -match '[":{}[\],&*#?|\-<>=!%@`]' -or $Value -match "'" -or $Value -match '\n') {
            $escaped = $Value.Replace("'", "''")
            return "'$escaped'"
        }
        return "`"$Value`""
    }
    
    $secretsYaml = "    - name: acr-password`n      value: $(ConvertTo-YamlSafeString $ACR_PASSWORD)"
    foreach ($key in $envVars.Keys) {
        $value = $envVars[$key]
        $secretName = $key.ToLower().Replace("_", "-")
        if ($secretVars -contains $key) {
            $safeValue = ConvertTo-YamlSafeString $value
            $secretsYaml += "`n    - name: $secretName`n      value: $safeValue"
        }
    }
    
    $envVarsYaml = ""
    foreach ($key in $envVars.Keys) {
        $value = $envVars[$key]
        $secretName = $key.ToLower().Replace("_", "-")
        if ($secretVars -contains $key) {
            $envVarsYaml += "      - name: $key`n        secretRef: $secretName`n"
        } else {
            $safeValue = ConvertTo-YamlSafeString $value
            $envVarsYaml += "      - name: $key`n        value: $safeValue`n"
        }
    }
    
    $yamlContent = @"
properties:
  managedEnvironmentId: /subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/managedEnvironments/$ENVIRONMENT_NAME
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8081
      transport: auto
      allowInsecure: false
    registries:
    - server: $ACR_LOGIN_SERVER
      username: $ACR_USERNAME
      passwordSecretRef: acr-password
    secrets:
$secretsYaml
  template:
    containers:
    - image: ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}
      name: $CONTAINER_APP_NAME
      resources:
        cpu: 0.5
        memory: 1Gi
      env:
$envVarsYaml
    scale:
      minReplicas: 1
      maxReplicas: 3
"@
    
    $yamlFile = "containerapp-config.yaml"
    [System.IO.File]::WriteAllText($yamlFile, $yamlContent, [System.Text.UTF8Encoding]::new($false))
    Write-Host "  Configuration saved to $yamlFile" -ForegroundColor Gray

    # Step 6: Create Container App
    if ($startStep -le 5) {
        Write-Host ""
        Write-Host "[Step 6/7] Creating Container App..." -ForegroundColor Cyan
        
        $appExists = az containerapp show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --query "name" -o tsv 2>$null
        
        if ($appExists) {
            Write-Host "Container App '$CONTAINER_APP_NAME' already exists, updating with YAML..." -ForegroundColor Yellow
            az containerapp update `
                --name $CONTAINER_APP_NAME `
                --resource-group $RESOURCE_GROUP `
                --yaml $yamlFile `
                --output none
            Test-AzCommandSuccess "Container App update"
            
            Write-Host "Forcing new revision with updated image..." -ForegroundColor Cyan
            az containerapp update `
                --name $CONTAINER_APP_NAME `
                --resource-group $RESOURCE_GROUP `
                --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" `
                --output none
            Test-AzCommandSuccess "Container App image update"
        } else {
            Write-Host "Creating Container App from YAML configuration..." -ForegroundColor Gray
            az containerapp create `
                --name $CONTAINER_APP_NAME `
                --resource-group $RESOURCE_GROUP `
                --environment $ENVIRONMENT_NAME `
                --yaml $yamlFile `
                --output none
            Test-AzCommandSuccess "Container App creation"
        }
        
        Remove-Item $yamlFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "[Step 6/7] Skipped (Container App)" -ForegroundColor Gray
    }

    # Step 7: Get the Application URL
    Write-Host ""
    Write-Host "[Step 7/7] Getting Application URL..." -ForegroundColor Cyan
    
    Start-Sleep -Seconds 5
    
    $APP_FQDN = az containerapp show `
        --name $CONTAINER_APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --query "properties.configuration.ingress.fqdn" -o tsv
    
    if (-not $APP_FQDN) {
        Write-Host "WARNING: Could not retrieve application URL. The app may still be provisioning." -ForegroundColor Yellow
        $APP_FQDN = "<pending>"
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Deployment Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "URL for Simulator (WebSocket):" -ForegroundColor Yellow
    Write-Host "  wss://$APP_FQDN" -ForegroundColor White
    Write-Host ""
    Write-Host "Health Check:" -ForegroundColor Yellow
    Write-Host "  https://$APP_FQDN/health" -ForegroundColor White
    Write-Host ""
    Write-Host "--- Useful Commands ---" -ForegroundColor Magenta
    Write-Host "View logs:        az containerapp logs show -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP --follow"
    Write-Host "Check status:     az containerapp show -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP"
}
else {
    Write-Host "Invalid choice. Please run the script again and enter 1 or 2." -ForegroundColor Red
    exit 1
}
