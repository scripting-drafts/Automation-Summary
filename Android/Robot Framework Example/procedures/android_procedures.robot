*** Settings ***
Library           ../pages/android_device_page.py

*** Keywords ***
List All Devices
    ${devices}=    List Devices
    [Return]       ${devices}

Reboot All Devices
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Reboot Device    ${device}
    END

Set All Devices To WiFi
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Set Wifi    ${device}
    END

Set All Devices To Default Network
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Set Default Network    ${device}
    END

Install Client On All Devices
    [Arguments]    ${apk_path}
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Install Client    ${device}    ${apk_path}
    END

Uninstall Client From All Devices
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Uninstall Client    ${device}
    END

Send SOS To All Devices
    ${devices}=    List Devices
    FOR    ${device}    IN    @{devices}
        Send Sos    ${device}
    END
