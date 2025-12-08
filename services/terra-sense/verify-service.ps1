#!/usr/bin/env pwsh
# ============================================
# Terra-Sense Service Verification Script
# ============================================

Write-Host "🔍 Verifying Terra-Sense Implementation..." -ForegroundColor Cyan
Write-Host ""

$servicePath = "services/terra-sense"
$errors = @()
$warnings = @()

# Check directory exists
if (-not (Test-Path $servicePath)) {
    Write-Host "❌ Service directory not found: $servicePath" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Service directory exists" -ForegroundColor Green

# Check build files
$buildFiles = @(
    "build.gradle",
    "settings.gradle",
    "Dockerfile"
)

foreach ($file in $buildFiles) {
    $path = Join-Path $servicePath $file
    if (Test-Path $path) {
        Write-Host "✅ $file exists" -ForegroundColor Green
    } else {
        $errors += "Missing file: $file"
        Write-Host "❌ $file NOT FOUND" -ForegroundColor Red
    }
}

# Check Java source files
$javaFiles = @{
    "TerraSenseApplication.java" = "src/main/java/com/terraneuron/sense/TerraSenseApplication.java"
    "SensorData.java" = "src/main/java/com/terraneuron/sense/model/SensorData.java"
    "KafkaProducerService.java" = "src/main/java/com/terraneuron/sense/service/KafkaProducerService.java"
    "IngestionController.java" = "src/main/java/com/terraneuron/sense/controller/IngestionController.java"
    "KafkaConfig.java" = "src/main/java/com/terraneuron/sense/config/KafkaConfig.java"
}

Write-Host ""
Write-Host "Checking Java source files..." -ForegroundColor Yellow

foreach ($file in $javaFiles.GetEnumerator()) {
    $path = Join-Path $servicePath $file.Value
    if (Test-Path $path) {
        $lineCount = (Get-Content $path).Count
        Write-Host "✅ $($file.Key) exists ($lineCount lines)" -ForegroundColor Green
    } else {
        $errors += "Missing Java file: $($file.Key)"
        Write-Host "❌ $($file.Key) NOT FOUND" -ForegroundColor Red
    }
}

# Check configuration
$configPath = Join-Path $servicePath "src/main/resources/application.properties"
if (Test-Path $configPath) {
    Write-Host "✅ application.properties exists" -ForegroundColor Green
    
    # Check for required properties
    $content = Get-Content $configPath -Raw
    $requiredProps = @(
        "spring.kafka.bootstrap-servers",
        "kafka.topic.raw-sensor-data",
        "server.port"
    )
    
    foreach ($prop in $requiredProps) {
        if ($content -match $prop) {
            Write-Host "  ✓ Property configured: $prop" -ForegroundColor Gray
        } else {
            $warnings += "Missing property: $prop"
            Write-Host "  ⚠ Property missing: $prop" -ForegroundColor Yellow
        }
    }
} else {
    $errors += "Missing application.properties"
    Write-Host "❌ application.properties NOT FOUND" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "📊 VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "✅ All checks passed! Service is ready." -ForegroundColor Green
    Write-Host ""
    Write-Host "🚀 Next steps:" -ForegroundColor Cyan
    Write-Host "   1. Build: cd $servicePath && ./gradlew build" -ForegroundColor White
    Write-Host "   2. Run: ./gradlew bootRun" -ForegroundColor White
    Write-Host "   3. Test: curl http://localhost:8081/api/v1/ingest/health" -ForegroundColor White
    Write-Host ""
} else {
    if ($errors.Count -gt 0) {
        Write-Host "❌ $($errors.Count) Error(s) found:" -ForegroundColor Red
        foreach ($err in $errors) {
            Write-Host "   • $err" -ForegroundColor Red
        }
    }
    
    if ($warnings.Count -gt 0) {
        Write-Host "⚠ $($warnings.Count) Warning(s):" -ForegroundColor Yellow
        foreach ($warn in $warnings) {
            Write-Host "   • $warn" -ForegroundColor Yellow
        }
    }
    
    if ($errors.Count -gt 0) {
        exit 1
    }
}

Write-Host ""
