@echo off
rem Toggle network adapter on/off for the Wi-Fi-off demo.
rem Run with no args to check status, "off" to disable, "on" to enable.
rem Requires admin (UAC prompt) because disabling adapters needs elevation.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting admin to toggle network adapter...
    powershell -Command "Start-Process '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
)

rem Find the first active Ethernet or Wi-Fi adapter
for /f "tokens=*" %%a in ('powershell -Command "Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and ($_.InterfaceDescription -like '*Ethernet*' -or $_.InterfaceDescription -like '*Wi-Fi*' -or $_.InterfaceDescription -like '*Realtek*' -or $_.InterfaceDescription -like '*Intel*' -or $_.InterfaceDescription -like '*Marvell*' -or $_.InterfaceDescription -like '*Broadcom*')} | Select-Object -First 1 -ExpandProperty Name"') do set ADAPTER=%%a

if "%ADAPTER%"=="" (
    echo No active network adapter found.
    pause
    exit /b 1
)

if /i "%1"=="off" (
    echo Disabling: %ADAPTER%
    netsh interface set interface "%ADAPTER%" admin=disable
    echo DONE — %ADAPTER% is OFF. Internet is dead.
    timeout /t 3 >nul
    exit /b 0
)

if /i "%1"=="on" (
    echo Enabling: %ADAPTER%
    netsh interface set interface "%ADAPTER%" admin=enable
    echo DONE — %ADAPTER% is ON. Internet is back.
    timeout /t 3 >nul
    exit /b 0
)

rem No argument — just show status
echo Active adapter: %ADAPTER%
netsh interface show interface name="%ADAPTER%"
echo.
echo Run "net_toggle.bat off" to disable internet (for the demo)
echo Run "net_toggle.bat on" to re-enable internet
pause
