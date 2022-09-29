import { Component, Input, Output, OnDestroy, EventEmitter } from '@angular/core';

import { MessageService } from 'primeng/api'

import { Subscription } from 'rxjs'

import { UsersService } from '../backend/api/users.service'

@Component({
  selector: 'app-change-passwd-dlg',
  templateUrl: './change-passwd-dlg.component.html',
  styleUrls: ['./change-passwd-dlg.component.sass']
})
export class ChangePasswdDlgComponent implements OnDestroy {
    @Input() user: any
    @Input() show: any
    @Output() showChange = new EventEmitter<boolean>();

    private subs: Subscription = new Subscription()

    passwordOld: string
    passwordNew1: string
    passwordNew2: string

    constructor(
        protected usersService: UsersService,
        private msgSrv: MessageService,
    ) { }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    changePassword() {
        if (this.passwordNew1 !== this.passwordNew2) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Changing password erred',
                detail: 'New passwords are not the same',
                life: 10000,
            })
            return
        }
        if (!this.passwordNew1) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Changing password erred',
                detail: 'New password cannot be empty',
                life: 10000,
            })
            return
        }

        const passwds = {
            password_old: this.passwordOld,
            password_new: this.passwordNew1,
        }
        this.subs.add(
            this.usersService
                .changePassword(this.user.id, passwds)
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Password changed',
                            detail: 'Changing password succeeded.',
                        })
                        this.show = false
                        this.showChange.emit(this.show);
                        this.passwordOld = ''
                        this.passwordNew1 = ''
                        this.passwordNew2 = ''
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Changing password erred',
                            detail: 'Changing password erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    passwdChangeKeyUp(evKey) {
        if (evKey === 'Enter') {
            this.changePassword()
        }
    }

    cancel() {
        this.show = false
        this.showChange.emit(this.show);
    }

    onHide() {
        this.show = false
        this.showChange.emit(this.show);
    }
}
