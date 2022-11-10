import { ComponentFixture, TestBed } from '@angular/core/testing'

import { ChangePasswdDlgComponent } from './change-passwd-dlg.component'

describe('ChangePasswdDlgComponent', () => {
    let component: ChangePasswdDlgComponent
    let fixture: ComponentFixture<ChangePasswdDlgComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [ChangePasswdDlgComponent],
        }).compileComponents()

        fixture = TestBed.createComponent(ChangePasswdDlgComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
