*** Settings ***
Resource    ../procedures/android_procedures.robot

*** Test Cases ***
Toggle Wifi And Default
    Set All Devices To WiFi
    Set All Devices To Default Network

Install And Remove Client
    ${apk}=    Set Variable    /path/to/client.apk
    Install Client On All Devices    ${apk}
    Uninstall Client From All Devices
