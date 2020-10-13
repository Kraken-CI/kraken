import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { RunBoxComponent } from './run-box.component'

describe('RunBoxComponent', () => {
    let component: RunBoxComponent
    let fixture: ComponentFixture<RunBoxComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [RunBoxComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(RunBoxComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
