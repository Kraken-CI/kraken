import { Injectable } from '@angular/core'
import { BehaviorSubject, Observable } from 'rxjs'
import { map } from 'rxjs/operators'

import { AuthService } from '../auth.service'
import { ManagementService } from '../backend/api/management.service'

@Injectable({
    providedIn: 'root',
})
export class SettingsService {
    private settingsSubject: BehaviorSubject<any>
    public settings: Observable<any>

    constructor(
        private auth: AuthService,
        private managementService: ManagementService
    ) {
        this.settingsSubject = new BehaviorSubject(null)
        this.settings = this.settingsSubject.asObservable()

        this.auth.currentSession.subscribe((session) => {
            if (!session) {
                return
            }
            this.managementService.getSettings().subscribe((settings) => {
                this.settingsSubject.next(settings)
            })
        })
    }

    updateSettings(settings) {
        return this.managementService.updateSettings(settings).pipe(
            map((settings2) => {
                this.settingsSubject.next(settings2)
                return settings2
            })
        )
    }
}
